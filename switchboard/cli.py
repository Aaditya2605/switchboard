from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import typer
import uvicorn

from switchboard.agent_kinds import default_registry
from switchboard.dashboard import create_app
from switchboard.db import AgentRepository, default_db_path, init_db, switchboard_home
from switchboard.launchd import DEFAULT_LABEL, LaunchdInstaller
from switchboard.presets import workflows_for_profile
from switchboard.scheduler import Scheduler
from switchboard.service import SwitchboardService
from switchboard.telegram import handle_telegram_command
from switchboard.telegram_bot import TelegramBot, load_bot_config
from switchboard.tmux import TmuxClient

app = typer.Typer(help="Switchboard: command center for Claude Code and Codex agents.")
task_app = typer.Typer(help="Shared Kanban task board.")
workflow_app = typer.Typer(help="Reusable workflow and cron prompt dispatch.")
scheduler_app = typer.Typer(help="Run due workflow prompts automatically.")
telegram_app = typer.Typer(help="Telegram/Hermes text-command bridge.")
worktree_app = typer.Typer(help="Per-agent git worktree isolation.")
app.add_typer(task_app, name="task")
app.add_typer(workflow_app, name="workflow")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(telegram_app, name="telegram")
app.add_typer(worktree_app, name="worktree")


def service() -> SwitchboardService:
    init_db(default_db_path())
    return SwitchboardService(
        AgentRepository(default_db_path()),
        TmuxClient(),
        agent_kinds=default_registry(),
    )


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def launchd_installer(label: str = DEFAULT_LABEL) -> LaunchdInstaller:
    return LaunchdInstaller(
        repo_path=Path.cwd(),
        home=switchboard_home(),
        launch_agents_dir=launch_agents_dir(),
        label=label,
    )


def telegram_bot() -> TelegramBot:
    return TelegramBot(load_bot_config())


def fail(exc: Exception) -> None:
    typer.echo(str(exc).strip('"'), err=True)
    raise typer.Exit(1)


@app.command()
def init() -> None:
    path = init_db(default_db_path())
    typer.echo(f"Initialized Switchboard at {path}")


@app.command("agents")
def agents_cmd() -> None:
    agents = service().list_agents()
    if not agents:
        typer.echo("No agents registered.")
        return
    for agent in agents:
        typer.echo(f"{agent.name}\t{agent.kind}\t{agent.status}\t{agent.workdir}")


@app.command("kinds")
def kinds_cmd() -> None:
    """List available agent kinds (builtin + ~/.switchboard/agent_kinds.toml + plugins)."""

    for kind in default_registry().all():
        desc = f"\t{kind.description}" if kind.description else ""
        typer.echo(f"{kind.name}\t{kind.command}{desc}")


@app.command()
def spawn(
    kind: str,
    name: str,
    workdir: str,
    dry_run: bool = typer.Option(False, help="Register only; do not start tmux."),
    worktree: bool = typer.Option(False, "--worktree", help="Create an isolated git worktree for this agent."),
    worktree_root: str | None = typer.Option(None, "--worktree-root", help="Override the worktree path. Defaults to $SWITCHBOARD_HOME/worktrees/<name>."),
    branch: str | None = typer.Option(None, "--branch", help="Branch name for the worktree (default: switchboard/<name>)."),
) -> None:
    try:
        agent = service().spawn(
            kind,
            name,
            workdir,
            dry_run=dry_run,
            worktree=worktree,
            worktree_root=worktree_root,
            branch=branch,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    suffix = " (dry-run)" if dry_run else ""
    if agent.worktree_path:
        typer.echo(
            f"Spawned {agent.kind} agent '{agent.name}' in {agent.tmux_session}{suffix}; "
            f"worktree={agent.worktree_path} branch={agent.worktree_branch}"
        )
    else:
        typer.echo(f"Spawned {agent.kind} agent '{agent.name}' in {agent.tmux_session}{suffix}")


@app.command()
def run(
    task_id: int,
    timeout: int = typer.Option(600, "--timeout", help="Subprocess timeout in seconds."),
    complete: bool = typer.Option(False, "--complete", help="Mark the task completed on a clean exit."),
) -> None:
    """Dispatch a task to its assigned agent's non-interactive CLI (claude -p / codex exec)."""

    try:
        task, comment = service().run_task(task_id, timeout=timeout, mark_completed=complete)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Task #{task.id} ({task.status}) ran via {comment.author}; comment #{comment.id} captured.")


@app.command()
def send(name: str, prompt: str) -> None:
    try:
        service().send(name, prompt)
    except KeyError as exc:
        fail(exc)
    typer.echo(f"Sent prompt to {name}")


@app.command()
def msg(from_agent: str, to_agent: str, body: str, deliver: bool = typer.Option(False, help="Immediately inject into recipient tmux session.")) -> None:
    try:
        message = service().message(from_agent, to_agent, body, deliver=deliver)
    except KeyError as exc:
        fail(exc)
    state = "Delivered" if message.delivered_at else "Queued"
    typer.echo(f"{state} message #{message.id} from {message.from_agent} to {message.to_agent}")


@app.command()
def inbox(agent: str) -> None:
    try:
        messages = service().inbox(agent)
    except KeyError as exc:
        fail(exc)
    if not messages:
        typer.echo(f"No pending messages for {agent}.")
        return
    for message in messages:
        typer.echo(f"#{message.id}\tfrom={message.from_agent}\t{message.body}")


@app.command()
def logs(name: str, lines: int = 120) -> None:
    try:
        typer.echo(service().logs(name, lines=lines))
    except KeyError as exc:
        fail(exc)


@app.command()
def stop(name: str) -> None:
    try:
        agent = service().stop(name)
    except KeyError as exc:
        fail(exc)
    typer.echo(f"Stopped {agent.name}")


@app.command()
def health(name: str | None = typer.Argument(None), all: bool = typer.Option(False, "--all", help="Check all registered agents.")) -> None:
    try:
        svc = service()
        agents = svc.sync_health() if all else [svc.health(name or "")]
    except KeyError as exc:
        fail(exc)
    for agent in agents:
        typer.echo(f"{agent.name}\t{agent.kind}\t{agent.status}\t{agent.tmux_session}")


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8765, "--port", help="Port to bind."),
    require_token: bool = typer.Option(False, "--require-token", help="Fail unless SWITCHBOARD_DASHBOARD_TOKEN is set."),
) -> None:
    auth_token = os.environ.get("SWITCHBOARD_DASHBOARD_TOKEN")
    if require_token and not auth_token:
        fail(ValueError("SWITCHBOARD_DASHBOARD_TOKEN is required"))
    uvicorn.run(create_app(service(), auth_token=auth_token), host=host, port=port)


@task_app.command("add")
def task_add(
    title: str,
    description: str = typer.Option("", "--description", "-d"),
    agent: str | None = typer.Option(None, "--agent", "-a"),
    priority: str = typer.Option("normal", "--priority", "-p"),
    repo: str | None = typer.Option(None, "--repo", "-r"),
    due: str | None = typer.Option(None, "--due", help="Due date as YYYY-MM-DD."),
) -> None:
    try:
        task = service().create_task(
            title,
            description=description,
            assigned_agent=agent,
            priority=priority,
            repo=repo,
            due_date=due,
        )
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Created task {format_task(task)}")


@task_app.command("list")
def task_list(status: str | None = typer.Option(None, "--status", "-s")) -> None:
    tasks = service().list_tasks(status=status)
    if not tasks:
        typer.echo("No tasks found.")
        return
    for task in tasks:
        typer.echo(format_task(task))


@task_app.command("assign")
def task_assign(task_id: int, agent: str) -> None:
    try:
        task = service().assign_task(task_id, agent)
    except KeyError as exc:
        fail(exc)
    typer.echo(f"Assigned task #{task.id} to {task.assigned_agent}")


@task_app.command("move")
def task_move(task_id: int, status: str) -> None:
    try:
        task = service().move_task(task_id, status)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Moved task #{task.id} to {task.status}")


@task_app.command("update")
def task_update(
    task_id: int,
    priority: str | None = typer.Option(None, "--priority", "-p"),
    repo: str | None = typer.Option(None, "--repo", "-r"),
    due: str | None = typer.Option(None, "--due", help="Due date as YYYY-MM-DD."),
) -> None:
    try:
        task = service().update_task_metadata(task_id, priority=priority, repo=repo, due_date=due)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Updated task {format_task(task)}")


@task_app.command("comment")
def task_comment(task_id: int, body: str, author: str = typer.Option("user", "--author", "-a")) -> None:
    try:
        comment = service().add_task_comment(task_id, author=author, body=body)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Added comment #{comment.id} to task #{comment.task_id}")


@task_app.command("comments")
def task_comments(task_id: int) -> None:
    try:
        comments = service().list_task_comments(task_id)
    except KeyError as exc:
        fail(exc)
    if not comments:
        typer.echo(f"No comments for task #{task_id}.")
        return
    for comment in comments:
        typer.echo(f"#{comment.id}\t{comment.created_at}\t{comment.author}\t{comment.body}")


def format_task(task) -> str:
    assignee = task.assigned_agent or "unassigned"
    repo = task.repo or "-"
    due = task.due_date or "-"
    return f"#{task.id}\t{task.status}\t{assignee}\t{task.priority}\trepo={repo}\tdue={due}\t{task.title}"


@workflow_app.command("add")
def workflow_add(
    name: str,
    agent: str = typer.Option(..., "--agent", "-a"),
    prompt: str = typer.Option(..., "--prompt", "-p"),
    cron: str = typer.Option(..., "--cron", "-c"),
) -> None:
    try:
        workflow = service().create_workflow(name, agent_name=agent, prompt=prompt, cron=cron)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Created workflow #{workflow.id}: {workflow.name} -> {workflow.agent_name} [{workflow.cron}]")


@workflow_app.command("list")
def workflow_list() -> None:
    workflows = service().list_workflows()
    if not workflows:
        typer.echo("No workflows found.")
        return
    for workflow in workflows:
        state = "enabled" if workflow.enabled else "disabled"
        typer.echo(f"#{workflow.id}\t{state}\t{workflow.name}\t{workflow.agent_name}\t{workflow.cron}")


@workflow_app.command("install-presets")
def workflow_install_presets(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent that should run the preset workflows."),
    profile: str = typer.Option("launch", "--profile", help="Preset profile: launch or daily."),
) -> None:
    presets = workflows_for_profile(profile)
    if not presets:
        raise typer.BadParameter("profile must be one of: daily, launch")
    svc = service()
    installed = []
    try:
        for preset in presets:
            workflow = svc.create_workflow(preset.name, agent_name=agent, prompt=preset.prompt, cron=preset.cron)
            installed.append(workflow.name)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Installed {len(installed)} {profile} preset workflow(s): {', '.join(installed)}")


@workflow_app.command("run")
def workflow_run(name: str) -> None:
    try:
        workflow = service().run_workflow(name)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Ran workflow {workflow.name} -> {workflow.agent_name}")


@workflow_app.command("disable")
def workflow_disable(name: str) -> None:
    try:
        workflow = service().disable_workflow(name)
    except KeyError as exc:
        fail(exc)
    typer.echo(f"Workflow {workflow.name} disabled")


@workflow_app.command("enable")
def workflow_enable(name: str) -> None:
    try:
        workflow = service().enable_workflow(name)
    except KeyError as exc:
        fail(exc)
    typer.echo(f"Workflow {workflow.name} enabled")


@scheduler_app.command("tick")
def scheduler_tick(now: str | None = typer.Option(None, "--now", help="ISO timestamp override for testing.")) -> None:
    try:
        dt = datetime.fromisoformat(now) if now else None
        ran = Scheduler(service()).tick(dt)
    except (KeyError, ValueError) as exc:
        fail(exc)
    names = ", ".join(workflow.name for workflow in ran) or "none"
    typer.echo(f"Ran {len(ran)} workflow(s): {names}")


@scheduler_app.command("daemon")
def scheduler_daemon(interval: int = typer.Option(60, "--interval", "-i", help="Seconds between scheduler ticks.")) -> None:
    if interval <= 0:
        raise typer.BadParameter("interval must be positive")
    typer.echo(f"Starting Switchboard scheduler daemon; interval={interval}s")
    scheduler = Scheduler(service())
    while True:
        ran = scheduler.tick()
        if ran:
            typer.echo(f"Ran {len(ran)} workflow(s): {', '.join(workflow.name for workflow in ran)}")
        time.sleep(interval)


@scheduler_app.command("install-launchd")
def scheduler_install_launchd(
    interval: int = typer.Option(60, "--interval", "-i", help="Seconds between scheduler ticks."),
    label: str = typer.Option(DEFAULT_LABEL, "--label", help="LaunchAgent label."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Write plist but do not call launchctl."),
) -> None:
    try:
        result = launchd_installer(label).install(interval=interval, dry_run=dry_run)
    except ValueError as exc:
        fail(exc)
    typer.echo(f"{result.action}: {result.plist_path}")
    for command in result.commands:
        typer.echo(command)


@scheduler_app.command("uninstall-launchd")
def scheduler_uninstall_launchd(
    label: str = typer.Option(DEFAULT_LABEL, "--label", help="LaunchAgent label."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan removal but do not call launchctl or delete plist."),
) -> None:
    result = launchd_installer(label).uninstall(dry_run=dry_run)
    typer.echo(f"{result.action}: {result.plist_path}")
    for command in result.commands:
        typer.echo(command)


@scheduler_app.command("launchd-status")
def scheduler_launchd_status(label: str = typer.Option(DEFAULT_LABEL, "--label", help="LaunchAgent label.")) -> None:
    status = launchd_installer(label).status()
    state = "installed" if status.installed else "not installed"
    typer.echo(f"{status.label}: {state} ({status.plist_path})")


@telegram_app.command("handle")
def telegram_handle(text: str) -> None:
    try:
        typer.echo(handle_telegram_command(service(), text))
    except (KeyError, ValueError) as exc:
        fail(exc)


@telegram_app.command("poll")
def telegram_poll(
    once: bool = typer.Option(False, "--once", help="Poll once and exit."),
    timeout: int = typer.Option(30, "--timeout", help="Long-poll timeout in seconds."),
) -> None:
    try:
        bot = telegram_bot()
        if once:
            handled = bot.poll_once(lambda text: handle_telegram_command(service(), text), timeout=timeout)
            typer.echo(f"Handled {handled} update(s)")
            return
        typer.echo("Starting Telegram polling. Press Ctrl+C to stop.")
        while True:
            handled = bot.poll_once(lambda text: handle_telegram_command(service(), text), timeout=timeout)
            if handled:
                typer.echo(f"Handled {handled} update(s)")
    except (KeyError, ValueError) as exc:
        fail(exc)


@telegram_app.command("set-webhook")
def telegram_set_webhook(url: str) -> None:
    try:
        telegram_bot().set_webhook(url)
    except ValueError as exc:
        fail(exc)
    typer.echo("Webhook set")


@telegram_app.command("delete-webhook")
def telegram_delete_webhook() -> None:
    try:
        telegram_bot().delete_webhook()
    except ValueError as exc:
        fail(exc)
    typer.echo("Webhook deleted")


@telegram_app.command("webhook-info")
def telegram_webhook_info() -> None:
    try:
        info = telegram_bot().webhook_info()
    except ValueError as exc:
        fail(exc)
    typer.echo(info)


@worktree_app.command("list")
def worktree_list() -> None:
    rows = service().list_worktrees()
    if not rows:
        typer.echo("No agent worktrees.")
        return
    for agent, info in rows:
        status = "(missing on disk)" if info is None else "ok"
        branch = agent.worktree_branch or "?"
        typer.echo(f"{agent.name}\t{branch}\t{agent.worktree_path}\t{status}")


@worktree_app.command("prune")
def worktree_prune(
    name: str,
    source: str | None = typer.Option(None, "--source", help="Override the source repo (auto-inferred when omitted)."),
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually delete the worktree."),
) -> None:
    if not confirm:
        typer.echo("Refusing to delete without --confirm. Re-run with --confirm to proceed.")
        raise typer.Exit(1)
    try:
        agent = service().prune_worktree(name, source_repo=source)
    except (KeyError, ValueError) as exc:
        fail(exc)
    typer.echo(f"Pruned worktree for agent '{agent.name}'")


if __name__ == "__main__":
    app()
