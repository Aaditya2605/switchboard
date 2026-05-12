import sqlite3

import pytest

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
    return service, db_path


def test_create_task_with_metadata(tmp_path):
    service, _ = make_service(tmp_path)

    task = service.create_task(
        "Fix auth",
        description="Run tests first",
        assigned_agent="backend",
        priority="high",
        repo="~/projects/api",
        due_date="2026-05-20",
    )

    assert task.priority == "high"
    assert task.repo == "~/projects/api"
    assert task.due_date == "2026-05-20"


def test_update_task_metadata(tmp_path):
    service, _ = make_service(tmp_path)
    task = service.create_task("Fix auth")

    updated = service.update_task_metadata(task.id, priority="urgent", repo="~/projects/api", due_date="2026-05-21")

    assert updated.priority == "urgent"
    assert updated.repo == "~/projects/api"
    assert updated.due_date == "2026-05-21"


def test_task_priority_and_due_date_are_validated(tmp_path):
    service, _ = make_service(tmp_path)

    with pytest.raises(ValueError):
        service.create_task("Fix auth", priority="someday")

    with pytest.raises(ValueError):
        service.create_task("Fix auth", due_date="tomorrow")


def test_add_and_list_task_comments(tmp_path):
    service, _ = make_service(tmp_path)
    task = service.create_task("Fix auth")

    comment = service.add_task_comment(task.id, "aaditya", "Need API schema first")

    assert comment.task_id == task.id
    assert comment.author == "aaditya"
    assert comment.body == "Need API schema first"
    assert service.list_task_comments(task.id) == [comment]


def test_existing_task_table_migrates_metadata_columns(tmp_path):
    db_path = tmp_path / "switchboard.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            assigned_agent TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT INTO tasks (title, description, status) VALUES ('Legacy', '', 'assigned')")
    conn.commit()
    conn.close()

    init_db(db_path)
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=FakeRunner()))

    task = service.list_tasks()[0]
    assert task.title == "Legacy"
    assert task.priority == "normal"
    assert task.repo is None
    assert task.due_date is None
