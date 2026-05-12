from switchboard.db import AgentRepository, init_db
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


def test_create_and_list_workflows(tmp_path):
    service, _ = make_service(tmp_path)

    workflow = service.create_workflow(
        "daily-check",
        agent_name="backend",
        prompt="Review open tasks and suggest next action",
        cron="0 9 * * *",
    )

    assert workflow.id is not None
    assert workflow.name == "daily-check"
    assert workflow.agent_name == "backend"
    assert workflow.prompt == "Review open tasks and suggest next action"
    assert workflow.cron == "0 9 * * *"
    assert workflow.enabled is True
    assert service.list_workflows() == [workflow]


def test_run_workflow_sends_prompt_to_agent_and_records_run(tmp_path):
    service, runner = make_service(tmp_path)
    service.create_workflow(
        "daily-check",
        agent_name="backend",
        prompt="Review open tasks",
        cron="0 9 * * *",
    )

    workflow = service.run_workflow("daily-check")

    assert workflow.last_run_at is not None
    assert any("Workflow: daily-check" in c and "Review open tasks" in c for c in runner.commands)


def test_disable_and_enable_workflow(tmp_path):
    service, _ = make_service(tmp_path)
    service.create_workflow("daily-check", agent_name="backend", prompt="Review", cron="0 9 * * *")

    disabled = service.disable_workflow("daily-check")
    enabled = service.enable_workflow("daily-check")

    assert disabled.enabled is False
    assert enabled.enabled is True


def test_disabled_workflow_cannot_run(tmp_path):
    service, _ = make_service(tmp_path)
    service.create_workflow("daily-check", agent_name="backend", prompt="Review", cron="0 9 * * *")
    service.disable_workflow("daily-check")

    try:
        service.run_workflow("daily-check")
    except ValueError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("disabled workflow should not run")


def test_workflow_cron_requires_five_fields(tmp_path):
    service, _ = make_service(tmp_path)

    try:
        service.create_workflow("daily-check", agent_name="backend", prompt="Review", cron="daily")
    except ValueError as exc:
        assert "cron" in str(exc)
    else:
        raise AssertionError("invalid cron should be rejected")
