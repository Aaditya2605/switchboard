from datetime import datetime
import subprocess

from switchboard.db import AgentRepository, init_db
from switchboard.service import SwitchboardService
from switchboard.telegram import handle_telegram_command
from switchboard.tmux import TmuxClient


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        if "tmux has-session" in command:
            raise subprocess.CalledProcessError(1, command)
        return ""


def make_service(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    runner = FakeRunner()
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=runner))
    service.spawn("claude", "backend", "/tmp/project", dry_run=True)
    service.spawn("codex", "reviewer", "/tmp/project", dry_run=True)
    return service, runner


def test_telegram_agents_lists_registered_agents(tmp_path):
    service, _ = make_service(tmp_path)

    response = handle_telegram_command(service, "/agents")

    assert "backend" in response
    assert "reviewer" in response


def test_telegram_tasks_lists_tasks_by_status(tmp_path):
    service, _ = make_service(tmp_path)
    service.create_task("Fix auth", assigned_agent="backend")
    service.create_task("Ship docs", assigned_agent="reviewer")
    service.move_task(2, "completed")

    response = handle_telegram_command(service, "/tasks completed")

    assert "Ship docs" in response
    assert "Fix auth" not in response


def test_telegram_inbox_shows_agent_messages(tmp_path):
    service, _ = make_service(tmp_path)
    service.message("reviewer", "backend", "Need schema")

    response = handle_telegram_command(service, "/inbox backend")

    assert "Need schema" in response
    assert "reviewer" in response


def test_telegram_send_dispatches_prompt_to_agent(tmp_path):
    service, runner = make_service(tmp_path)

    response = handle_telegram_command(service, "/send backend Run tests")

    assert "Sent" in response
    assert any("Run tests" in command for command in runner.commands)


def test_telegram_scheduler_tick_runs_due_workflow(tmp_path):
    service, runner = make_service(tmp_path)
    service.create_workflow("hourly", agent_name="backend", prompt="Review tasks", cron="0 * * * *")

    response = handle_telegram_command(service, "/scheduler tick", now=datetime(2026, 5, 12, 14, 0))

    assert "Ran 1" in response
    assert "hourly" in response
    assert any("Workflow: hourly" in command for command in runner.commands)


def test_telegram_health_checks_agent(tmp_path):
    service, _ = make_service(tmp_path)

    response = handle_telegram_command(service, "/health backend")

    assert "backend" in response
    assert "dead" in response


def test_telegram_help_and_unknown_command(tmp_path):
    service, _ = make_service(tmp_path)

    assert "/agents" in handle_telegram_command(service, "/help")
    assert "Unknown command" in handle_telegram_command(service, "/nope")
