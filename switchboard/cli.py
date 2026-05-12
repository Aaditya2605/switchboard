from __future__ import annotations

import typer

from switchboard.db import AgentRepository, default_db_path, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient

app = typer.Typer(help="Switchboard: command center for Claude Code and Codex agents.")
task_app = typer.Typer(help="Shared Kanban task board.")
app.add_typer(task_app, name="task")


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


if __name__ == "__main__":
    app()
