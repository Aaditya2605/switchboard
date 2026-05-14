from datetime import datetime

import pytest

from switchboard.db import AgentRepository, init_db
from switchboard.scheduler import Scheduler, cron_matches
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


def test_cron_matches_supports_weekday_range_using_cron_numbering():
    # 0 11 * * 1-5 → 11:00 Mon-Fri. Python weekday(): Mon=0, Tue=1, ..., Fri=4, Sat=5, Sun=6.
    cron = "0 11 * * 1-5"
    assert cron_matches(cron, datetime(2026, 5, 11, 11, 0))  # Monday
    assert cron_matches(cron, datetime(2026, 5, 15, 11, 0))  # Friday
    assert not cron_matches(cron, datetime(2026, 5, 16, 11, 0))  # Saturday
    assert not cron_matches(cron, datetime(2026, 5, 17, 11, 0))  # Sunday


def test_cron_matches_supports_step_syntax():
    cron = "*/15 * * * *"
    assert cron_matches(cron, datetime(2026, 5, 12, 9, 0))
    assert cron_matches(cron, datetime(2026, 5, 12, 9, 15))
    assert cron_matches(cron, datetime(2026, 5, 12, 9, 30))
    assert cron_matches(cron, datetime(2026, 5, 12, 9, 45))
    assert not cron_matches(cron, datetime(2026, 5, 12, 9, 16))


def test_cron_matches_supports_list_and_range_combinations():
    cron = "0,30 9-11 * * *"
    assert cron_matches(cron, datetime(2026, 5, 12, 9, 0))
    assert cron_matches(cron, datetime(2026, 5, 12, 11, 30))
    assert not cron_matches(cron, datetime(2026, 5, 12, 12, 0))
    assert not cron_matches(cron, datetime(2026, 5, 12, 9, 15))


def test_cron_matches_treats_zero_and_seven_as_sunday():
    # cron Sunday is 0 or 7; Python weekday() Sun = 6.
    assert cron_matches("0 9 * * 0", datetime(2026, 5, 17, 9, 0))  # Sunday
    assert cron_matches("0 9 * * 7", datetime(2026, 5, 17, 9, 0))  # Sunday again


def test_cron_matches_rejects_malformed_expressions():
    moment = datetime(2026, 5, 12, 9, 30)
    with pytest.raises(ValueError):
        cron_matches("0 9 * *", moment)
    with pytest.raises(ValueError):
        cron_matches("0 9 * * unknown", moment)
    with pytest.raises(ValueError):
        cron_matches("5-2 * * * *", moment)


def test_scheduler_runs_weekday_preset(tmp_path):
    service, runner = make_service(tmp_path)
    service.create_workflow("weekday-noon", agent_name="backend", prompt="Stand up", cron="0 11 * * 1-5")
    scheduler = Scheduler(service)

    monday = datetime(2026, 5, 11, 11, 0)
    saturday = datetime(2026, 5, 16, 11, 0)

    assert [workflow.name for workflow in scheduler.tick(monday)] == ["weekday-noon"]
    # second tick on Saturday should not re-run because the cron does not match
    assert scheduler.tick(saturday) == []
