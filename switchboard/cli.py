from __future__ import annotations

import time
from datetime import datetime

import typer

from switchboard.db import AgentRepository, default_db_path, init_db
from switchboard.scheduler import Scheduler
from switchboard.service import SwitchboardService
from switchboard.telegram import handle_telegram_command
from switchboard.tmux import TmuxClient

app = typer.Typer(help="Switchboard: command center for Claude Code and Codex agents.")
task_app = typer.Typer(help="Shared Kanban task board.")
workflow_app = typer.Typer(help="Reusable workflow and cron prompt dispatch.")
scheduler_app = typer.Typer(help="Run due workflow prompts automatically.")
telegram_app = typer.Typer(help="Telegram/Hermes text-command bridge.")
app.add_typer(task_app, name="task")
app.add_typer(workflow_app, name="workflow")
app.add_typer(scheduler_app, name="scheduler")
app.add_typer(telegram_app, name="telegram")


def service() -> SwitchboardService:
    init_db(default_db_path())
    return SwitchboardService(AgentRepository(default_db_path()), TmuxClient())


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


@app.command()
def spawn(kind: str, name: str, workdir: str, dry_run: bool = typer.Option(False, help="Register only; do not start tmux.")) -> None:
    try:
        agent = service().spawn(kind, name, workdir, dry_run=dry_run)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    suffix = " (dry-run)" if dry_run else ""
    typer.echo(f"Spawned {agent.kind} agent '{agent.name}' in {agent.tmux_session}{suffix}")


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


@task_app.command("add")
def task_add(title: str, description: str = typer.Option("", "--description", "-d"), agent: str | None = typer.Option(None, "--agent", "-a")) -> None:
    try:
        task = service().create_task(title, description=description, assigned_agent=agent)
    except KeyError as exc:
        fail(exc)
    assignee = task.assigned_agent or "unassigned"
    typer.echo(f"Created task #{task.id}: {task.title} [{task.status}] assigned={assignee}")


@task_app.command("list")
def task_list(status: str | None = typer.Option(None, "--status", "-s")) -> None:
    tasks = service().list_tasks(status=status)
    if not tasks:
        typer.echo("No tasks found.")
        return
    for task in tasks:
        assignee = task.assigned_agent or "unassigned"
        typer.echo(f"#{task.id}\t{task.status}\t{assignee}\t{task.title}")


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


@telegram_app.command("handle")
def telegram_handle(text: str) -> None:
    try:
        typer.echo(handle_telegram_command(service(), text))
    except (KeyError, ValueError) as exc:
        fail(exc)


if __name__ == "__main__":
    app()
