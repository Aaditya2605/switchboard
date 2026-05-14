from __future__ import annotations

from typing import Sequence

import pytest

from switchboard.agent_kinds import AgentKind, AgentKindRegistry
from switchboard.db import AgentRepository, init_db
from switchboard.service import OneShotResult, SwitchboardService
from switchboard.tmux import TmuxClient


class FakeTmuxRunner:
    def __init__(self):
        self.commands: list[str] = []

    def run(self, command):
        self.commands.append(command)
        return ""


class FakeOneShot:
    def __init__(self, result: OneShotResult | None = None):
        self.calls: list[tuple[Sequence[str], str, int]] = []
        self.result = result or OneShotResult(stdout="ok\n", stderr="", returncode=0)

    def __call__(self, args, cwd, timeout):
        self.calls.append((tuple(args), cwd, timeout))
        return self.result


def make_service(tmp_path, *, runner=None, registry=None):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    return SwitchboardService(
        AgentRepository(db_path),
        TmuxClient(runner=FakeTmuxRunner()),
        agent_kinds=registry,
        one_shot_runner=runner,
    )


def test_run_task_dispatches_with_kind_prefix_and_prompt(tmp_path):
    runner = FakeOneShot()
    service = make_service(tmp_path, runner=runner)
    service.spawn("claude", "builder", "/tmp/project", dry_run=True)
    task = service.create_task("Ship dashboard", description="multi-page", assigned_agent="builder", repo="~/proj")

    task_after, comment = service.run_task(task.id)

    assert runner.calls, "one-shot runner should be invoked"
    args, cwd, timeout = runner.calls[0]
    assert args[:2] == ("claude", "-p")
    assert "Ship dashboard" in args[-1]
    assert "multi-page" in args[-1]
    assert cwd == "/tmp/project"
    assert timeout == 600
    assert comment.author == "builder"
    assert comment.body.strip() == "ok"
    assert task_after.status == "in_progress"


def test_run_task_captures_stderr_when_stdout_empty(tmp_path):
    runner = FakeOneShot(OneShotResult(stdout="", stderr="boom\n", returncode=2))
    service = make_service(tmp_path, runner=runner)
    service.spawn("claude", "builder", "/tmp/project", dry_run=True)
    task = service.create_task("Fail it", assigned_agent="builder")

    task_after, comment = service.run_task(task.id)

    assert "[exit 2]" in comment.body
    assert "boom" in comment.body
    # Status moved to in_progress, but mark_completed=False so it stays there even on success.
    assert task_after.status == "in_progress"


def test_run_task_marks_completed_when_requested_and_clean(tmp_path):
    runner = FakeOneShot(OneShotResult(stdout="done", returncode=0))
    service = make_service(tmp_path, runner=runner)
    service.spawn("claude", "builder", "/tmp/project", dry_run=True)
    task = service.create_task("Quick task", assigned_agent="builder")

    task_after, _ = service.run_task(task.id, mark_completed=True)

    assert task_after.status == "completed"


def test_run_task_keeps_in_progress_when_command_fails(tmp_path):
    runner = FakeOneShot(OneShotResult(stdout="", stderr="oops", returncode=1))
    service = make_service(tmp_path, runner=runner)
    service.spawn("claude", "builder", "/tmp/project", dry_run=True)
    task = service.create_task("Flaky", assigned_agent="builder")

    task_after, _ = service.run_task(task.id, mark_completed=True)

    assert task_after.status == "in_progress"


def test_run_task_requires_assigned_agent(tmp_path):
    service = make_service(tmp_path)
    task = service.create_task("Lonely")
    with pytest.raises(ValueError):
        service.run_task(task.id)


def test_run_task_rejects_kind_without_one_shot(tmp_path):
    registry = AgentKindRegistry(
        kinds=[AgentKind(name="aider", command="aider"), AgentKind(name="claude", command="claude", one_shot=("claude", "-p"))]
    )
    service = make_service(tmp_path, registry=registry)
    service.spawn("aider", "pair", "/tmp/project", dry_run=True)
    task = service.create_task("Refactor", assigned_agent="pair")
    with pytest.raises(ValueError):
        service.run_task(task.id)


def test_run_task_does_not_re_move_when_already_in_progress(tmp_path):
    runner = FakeOneShot()
    service = make_service(tmp_path, runner=runner)
    service.spawn("claude", "builder", "/tmp/project", dry_run=True)
    task = service.create_task("Pre-moved", assigned_agent="builder")
    service.move_task(task.id, "in_progress")

    task_after, _ = service.run_task(task.id)
    assert task_after.status == "in_progress"


def test_run_tasks_in_parallel_dispatches_all_and_returns_per_task_status(tmp_path):
    runner = FakeOneShot(OneShotResult(stdout="hi", returncode=0))
    service = make_service(tmp_path, runner=runner)
    service.spawn("claude", "builder", "/tmp/project", dry_run=True)
    ids = []
    for n in range(4):
        task = service.create_task(f"Task {n}", assigned_agent="builder")
        ids.append(task.id)

    results = service.run_tasks_in_parallel(ids, timeout=30, max_workers=2)

    assert [r.task_id for r in results] == ids
    assert all(r.ok for r in results)
    assert all(r.status == "in_progress" for r in results)
    assert len(runner.calls) == 4


def test_run_tasks_in_parallel_isolates_failures(tmp_path):
    runner = FakeOneShot()
    service = make_service(tmp_path, runner=runner)
    service.spawn("claude", "builder", "/tmp/project", dry_run=True)
    good = service.create_task("Good", assigned_agent="builder")
    orphan = service.create_task("Orphan")  # no assignee

    results = service.run_tasks_in_parallel([good.id, orphan.id], timeout=30, max_workers=2)
    by_id = {r.task_id: r for r in results}

    assert by_id[good.id].ok is True
    assert by_id[orphan.id].ok is False
    assert "no assigned agent" in by_id[orphan.id].message.lower()


def test_run_tasks_in_parallel_rejects_invalid_max_workers(tmp_path):
    service = make_service(tmp_path)
    with pytest.raises(ValueError):
        service.run_tasks_in_parallel([1], max_workers=0)
