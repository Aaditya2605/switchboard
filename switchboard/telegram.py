from __future__ import annotations

import shlex
from datetime import datetime

from switchboard.scheduler import Scheduler
from switchboard.service import SwitchboardService


HELP_TEXT = """Switchboard commands:
/agents
/tasks [status]
/inbox AGENT
/send AGENT PROMPT...
/scheduler tick
/help"""


def handle_telegram_command(service: SwitchboardService, text: str, now: datetime | None = None) -> str:
    try:
        parts = shlex.split(text.strip())
    except ValueError as exc:
        return f"Parse error: {exc}"
    if not parts:
        return HELP_TEXT

    command = parts[0].removeprefix("/sheaf").removeprefix("/switchboard")
    if command in {"", "/help", "help"}:
        return HELP_TEXT
    if command == "/agents":
        return _format_agents(service)
    if command == "/tasks":
        status = parts[1] if len(parts) > 1 else None
        return _format_tasks(service, status=status)
    if command == "/inbox":
        if len(parts) != 2:
            return "Usage: /inbox AGENT"
        return _format_inbox(service, parts[1])
    if command == "/send":
        if len(parts) < 3:
            return "Usage: /send AGENT PROMPT..."
        agent = parts[1]
        prompt = " ".join(parts[2:])
        service.send(agent, prompt)
        return f"Sent prompt to {agent}"
    if command == "/scheduler":
        if len(parts) == 2 and parts[1] == "tick":
            ran = Scheduler(service).tick(now)
            names = ", ".join(workflow.name for workflow in ran) or "none"
            return f"Ran {len(ran)} workflow(s): {names}"
        return "Usage: /scheduler tick"
    return f"Unknown command: {parts[0]}\n\n{HELP_TEXT}"


def _format_agents(service: SwitchboardService) -> str:
    agents = service.list_agents()
    if not agents:
        return "No agents registered."
    return "\n".join(f"{agent.name} — {agent.kind} — {agent.status}" for agent in agents)


def _format_tasks(service: SwitchboardService, status: str | None = None) -> str:
    tasks = service.list_tasks(status=status)
    if not tasks:
        return "No tasks found."
    return "\n".join(
        f"#{task.id} {task.status} {task.assigned_agent or 'unassigned'} — {task.title}" for task in tasks
    )


def _format_inbox(service: SwitchboardService, agent: str) -> str:
    messages = service.inbox(agent)
    if not messages:
        return f"No pending messages for {agent}."
    return "\n".join(f"#{message.id} from {message.from_agent}: {message.body}" for message in messages)
