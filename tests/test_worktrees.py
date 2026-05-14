from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from switchboard.db import AgentRepository, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient
from switchboard.worktrees import GitWorktrees, WorktreeError, WorktreeInfo, _parse_porcelain


@dataclass
class FakeResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Captures git invocations and returns scripted results."""

    def __init__(self, responses: list[FakeResult] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.responses = list(responses or [])
        self.default = FakeResult()

    def run(self, cmd):
        self.calls.append(cmd)
        if self.responses:
            return self.responses.pop(0)
        return self.default


class FakeTmux:
    def __init__(self):
        self.started: list[tuple[str, str, str]] = []

    def start_agent(self, session, kind, workdir):
        self.started.append((session, kind, workdir))

    def send(self, session, prompt):
        pass

    def logs(self, session, lines=120):
        return ""

    def stop(self, session):
        pass

    def exists(self, session):
        return True


def init_real_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    (path / "README.md").write_text("hello\n")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)
    return path


def test_create_rejects_non_repo(tmp_path):
    runner = RecordingRunner()
    wt = GitWorktrees(runner=runner)
    with pytest.raises(WorktreeError):
        wt.create(tmp_path / "missing", tmp_path / "out", "branch")


def test_create_invokes_git_worktree_add(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    (source / ".git").mkdir()
    runner = RecordingRunner([FakeResult(0, "", "")])
    wt = GitWorktrees(runner=runner)
    info = wt.create(source, tmp_path / "wt", "switchboard/builder")
    assert info.path == tmp_path / "wt"
    assert info.branch == "switchboard/builder"
    assert runner.calls[0] == [
        "git",
        "-C",
        str(source),
        "worktree",
        "add",
        "-b",
        "switchboard/builder",
        str(tmp_path / "wt"),
        "HEAD",
    ]


def test_create_attaches_to_existing_branch_on_conflict(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    (source / ".git").mkdir()
    runner = RecordingRunner([
        FakeResult(1, "", "fatal: A branch named 'switchboard/x' already exists"),
        FakeResult(0, "", ""),
    ])
    wt = GitWorktrees(runner=runner)
    info = wt.create(source, tmp_path / "wt", "switchboard/x")
    assert info.branch == "switchboard/x"
    assert "-b" not in runner.calls[1]


def test_create_rejects_existing_nonempty_target(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    (source / ".git").mkdir()
    target = tmp_path / "wt"
    target.mkdir()
    (target / "stray").write_text("x")
    wt = GitWorktrees(runner=RecordingRunner())
    with pytest.raises(WorktreeError):
        wt.create(source, target, "branch")


def test_parse_porcelain_extracts_path_and_branch():
    output = (
        "worktree /repo\nHEAD abc123\nbranch refs/heads/main\n\n"
        "worktree /tmp/wt\nHEAD def456\nbranch refs/heads/feature\n\n"
        "worktree /tmp/detached\nHEAD 0\ndetached\n"
    )
    parsed = _parse_porcelain(output.splitlines())
    assert [(str(w.path), w.branch) for w in parsed] == [
        ("/repo", "main"),
        ("/tmp/wt", "feature"),
        ("/tmp/detached", "(detached)"),
    ]


def test_worktrees_remove_falls_back_to_rmtree_on_failure(tmp_path):
    source = tmp_path / "repo"
    source.mkdir()
    target = tmp_path / "wt"
    target.mkdir()
    (target / "stray").write_text("x")
    runner = RecordingRunner([
        FakeResult(1, "", "fatal: cannot remove"),
        FakeResult(0, "", ""),  # prune succeeds
    ])
    GitWorktrees(runner=runner).remove(source, target)
    assert not target.exists()


# ----- End-to-end integration through SwitchboardService against a real git repo -----


def make_service(tmp_path, repo: Path) -> SwitchboardService:
    home = tmp_path / "switchboard-home"
    home.mkdir(parents=True, exist_ok=True)
    db_path = home / "switchboard.db"
    init_db(db_path)
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=FakeTmux()), worktrees=GitWorktrees())
    return service, home


def test_spawn_with_worktree_creates_isolated_checkout(tmp_path, monkeypatch):
    repo = init_real_repo(tmp_path / "repo")
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path / "switchboard-home"))
    service, home = make_service(tmp_path, repo)

    agent = service.spawn("claude", "builder", str(repo), dry_run=True, worktree=True)

    assert agent.worktree_path is not None
    assert agent.worktree_branch == "switchboard/builder"
    worktree_path = Path(agent.worktree_path)
    assert worktree_path.exists()
    assert worktree_path != repo
    # README from source repo should be visible in worktree
    assert (worktree_path / "README.md").read_text() == "hello\n"


def test_prune_worktree_removes_checkout(tmp_path, monkeypatch):
    repo = init_real_repo(tmp_path / "repo")
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path / "switchboard-home"))
    service, home = make_service(tmp_path, repo)

    service.spawn("claude", "builder", str(repo), dry_run=True, worktree=True)
    agent_after = service.prune_worktree("builder", source_repo=str(repo))

    assert agent_after.worktree_path is None
    assert agent_after.worktree_branch is None


def test_list_worktrees_filters_to_agents_with_worktree(tmp_path, monkeypatch):
    repo = init_real_repo(tmp_path / "repo")
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path / "switchboard-home"))
    service, _ = make_service(tmp_path, repo)

    service.spawn("claude", "plain", str(repo), dry_run=True)
    service.spawn("codex", "isolated", str(repo), dry_run=True, worktree=True)

    rows = service.list_worktrees()
    names = [agent.name for agent, _ in rows]
    assert names == ["isolated"]


def test_spawn_records_default_workdir_when_worktree_disabled(tmp_path):
    repo = init_real_repo(tmp_path / "repo")
    service, _ = make_service(tmp_path, repo)
    agent = service.spawn("claude", "plain", str(repo), dry_run=True)
    assert agent.worktree_path is None
    assert agent.worktree_branch is None
    assert agent.workdir == str(repo)
