from switchboard.db import AgentRepository, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient


class FakeRunner:
    def run(self, command):
        return ""


def make_service(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=FakeRunner()))
    service.spawn("claude", "backend", "/tmp/project", dry_run=True)
    return service


def test_create_and_list_tasks(tmp_path):
    service = make_service(tmp_path)

    task = service.create_task("Fix auth", description="Run failing tests first")

    assert task.id is not None
    assert task.title == "Fix auth"
    assert task.status == "assigned"
    assert service.list_tasks() == [task]


def test_assign_task_to_agent(tmp_path):
    service = make_service(tmp_path)
    task = service.create_task("Fix auth")

    updated = service.assign_task(task.id, "backend")

    assert updated.assigned_agent == "backend"


def test_move_task_status(tmp_path):
    service = make_service(tmp_path)
    task = service.create_task("Fix auth")

    updated = service.move_task(task.id, "in_progress")
    done = service.move_task(task.id, "completed")

    assert updated.status == "in_progress"
    assert done.status == "completed"
    assert service.list_tasks(status="completed") == [done]
