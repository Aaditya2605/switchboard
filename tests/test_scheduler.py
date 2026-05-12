from datetime import datetime

from switchboard.db import AgentRepository, init_db
from switchboard.scheduler import Scheduler
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        return ""


def make_service(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    runner = FakeRunner()
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=runner))
    service.spawn("claude", "backend", "/tmp/project", dry_run=True)
    return service, runner


def test_scheduler_tick_runs_due_workflow_once_per_matching_minute(tmp_path):
    service, runner = make_service(tmp_path)
    service.create_workflow("nine-am", agent_name="backend", prompt="Review tasks", cron="30 9 * * *")
    scheduler = Scheduler(service)
    now = datetime(2026, 5, 12, 9, 30)

    ran = scheduler.tick(now)
    ran_again = scheduler.tick(now)

    assert [workflow.name for workflow in ran] == ["nine-am"]
    assert ran_again == []
    assert sum("Workflow: nine-am" in command for command in runner.commands) == 1


def test_scheduler_tick_skips_not_due_and_disabled_workflows(tmp_path):
    service, runner = make_service(tmp_path)
    service.create_workflow("nine-am", agent_name="backend", prompt="Review tasks", cron="30 9 * * *")
    service.create_workflow("disabled", agent_name="backend", prompt="Nope", cron="15 10 * * *")
    service.disable_workflow("disabled")
    scheduler = Scheduler(service)

    ran = scheduler.tick(datetime(2026, 5, 12, 10, 15))

    assert ran == []
    assert not any("Workflow: disabled" in command for command in runner.commands)


def test_scheduler_supports_wildcards(tmp_path):
    service, runner = make_service(tmp_path)
    service.create_workflow("hourly", agent_name="backend", prompt="Review tasks", cron="0 * * * *")
    scheduler = Scheduler(service)

    ran = scheduler.tick(datetime(2026, 5, 12, 14, 0))

    assert [workflow.name for workflow in ran] == ["hourly"]
    assert any("Workflow: hourly" in command for command in runner.commands)
