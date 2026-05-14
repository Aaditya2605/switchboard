"""Git worktree management for per-agent isolation.

Switchboard spawns multiple Claude/Codex agents against the same repo. Without
isolation they trip over each other's working trees. Each agent can instead
operate inside its own ``git worktree``, sharing the underlying ``.git``
directory but with a distinct branch and checkout path.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol


class WorktreeError(RuntimeError):
    """Raised when a git worktree operation fails."""


@dataclass(frozen=True)
class WorktreeInfo:
    path: Path
    branch: str
    head: str | None = None


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, cmd: list[str]) -> CommandResult: ...  # pragma: no cover - protocol


class _SubprocessRunner:
    def run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, capture_output=True, text=True)


class GitWorktrees:
    """Thin wrapper around ``git worktree`` for switchboard's isolation needs."""

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self._runner: CommandRunner = runner or _SubprocessRunner()

    def is_repo(self, source: Path) -> bool:
        if not source.exists():
            return False
        git_marker = source / ".git"
        if git_marker.is_dir() or git_marker.is_file():
            return True
        # ``git rev-parse`` handles bare repos and worktrees correctly.
        result = self._runner.run(["git", "-C", str(source), "rev-parse", "--is-inside-work-tree"])
        return result.returncode == 0 and result.stdout.strip() == "true"

    def create(self, source: Path, target: Path, branch: str) -> WorktreeInfo:
        if not source.exists():
            raise WorktreeError(f"source repo does not exist: {source}")
        if not self.is_repo(source):
            raise WorktreeError(f"not a git repo: {source}")
        if target.exists():
            if any(target.iterdir()):
                raise WorktreeError(f"worktree path already exists and is not empty: {target}")
            target.rmdir()
        target.parent.mkdir(parents=True, exist_ok=True)

        # First try to create a new branch from HEAD.
        result = self._runner.run(
            ["git", "-C", str(source), "worktree", "add", "-b", branch, str(target), "HEAD"]
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").lower()
            # Branch already exists or somebody else owns it — attach without -b.
            if "already exists" in stderr or "already used" in stderr or "is already checked out" in stderr:
                result = self._runner.run(
                    ["git", "-C", str(source), "worktree", "add", str(target), branch]
                )
        if result.returncode != 0:
            raise WorktreeError(
                f"git worktree add failed for {target} on {branch}: {(result.stderr or result.stdout).strip()}"
            )
        return WorktreeInfo(path=target, branch=branch)

    def remove(self, source: Path, target: Path, force: bool = True) -> None:
        if not target.exists():
            # Nothing to remove on disk; still prune metadata.
            self._runner.run(["git", "-C", str(source), "worktree", "prune"])
            return
        cmd = ["git", "-C", str(source), "worktree", "remove"]
        if force:
            cmd.append("--force")
        cmd.append(str(target))
        result = self._runner.run(cmd)
        if result.returncode != 0:
            if force and target.exists():
                # Last resort: drop the directory and prune metadata.
                shutil.rmtree(target, ignore_errors=True)
                prune = self._runner.run(["git", "-C", str(source), "worktree", "prune"])
                if prune.returncode != 0:
                    raise WorktreeError(
                        f"git worktree prune failed after manual cleanup: {prune.stderr.strip()}"
                    )
                return
            raise WorktreeError(
                f"git worktree remove failed for {target}: {(result.stderr or result.stdout).strip()}"
            )

    def list(self, source: Path) -> list[WorktreeInfo]:
        result = self._runner.run(["git", "-C", str(source), "worktree", "list", "--porcelain"])
        if result.returncode != 0:
            raise WorktreeError(
                f"git worktree list failed for {source}: {(result.stderr or result.stdout).strip()}"
            )
        return _parse_porcelain(result.stdout.splitlines())


def _parse_porcelain(lines: Iterable[str]) -> list[WorktreeInfo]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)

    result: list[WorktreeInfo] = []
    for block in blocks:
        path: Path | None = None
        branch = "(detached)"
        head: str | None = None
        for line in block:
            if line.startswith("worktree "):
                path = Path(line[len("worktree ") :])
            elif line.startswith("HEAD "):
                head = line[len("HEAD ") :]
            elif line.startswith("branch "):
                # e.g. "branch refs/heads/main" — normalise to short name.
                ref = line[len("branch ") :]
                branch = ref[len("refs/heads/") :] if ref.startswith("refs/heads/") else ref
            elif line == "detached":
                branch = "(detached)"
        if path is not None:
            result.append(WorktreeInfo(path=path, branch=branch, head=head))
    return result
