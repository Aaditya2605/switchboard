from __future__ import annotations

import typer

from switchboard.db import AgentRepository, default_db_path, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient

app = typer.Typer(help="Switchboard: command center for Claude Code and Codex agents.")


def service() -> SwitchboardService:
    init_db(default_db_path())
    return SwitchboardService(AgentRepository(default_db_path()), TmuxClient())


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
        typer.echo(str(exc).strip('"'), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Sent prompt to {name}")


@app.command()
def logs(name: str, lines: int = 120) -> None:
    try:
        typer.echo(service().logs(name, lines=lines))
    except KeyError as exc:
        typer.echo(str(exc).strip('"'), err=True)
        raise typer.Exit(1) from exc


@app.command()
def stop(name: str) -> None:
    try:
        agent = service().stop(name)
    except KeyError as exc:
        typer.echo(str(exc).strip('"'), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Stopped {agent.name}")


if __name__ == "__main__":
    app()
