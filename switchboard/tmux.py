from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass


class SubprocessRunner:
    def run(self, command: str) -> str:
        completed = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return completed.stdout


@dataclass
class TmuxClient:
    runner: object | None = None

    def __post_init__(self) -> None:
        if self.runner is None:
            self.runner = SubprocessRunner()

    def start_agent(self, session: str, kind: str, workdir: str) -> None:
        command = self._agent_command(kind)
        shell = f"cd {shlex.quote(workdir)} && {command}"
        self.runner.run(
            f"tmux new-session -d -s {shlex.quote(session)} {shlex.quote(shell)}"
        )

    def send(self, session: str, prompt: str) -> None:
        self.runner.run(
            f"tmux send-keys -t {shlex.quote(session)} {shlex.quote(prompt)} Enter"
        )

    def logs(self, session: str, lines: int = 120) -> str:
        return self.runner.run(
            f"tmux capture-pane -t {shlex.quote(session)} -p -S -{int(lines)}"
        )

    def stop(self, session: str) -> None:
        self.runner.run(f"tmux kill-session -t {shlex.quote(session)}")

    def exists(self, session: str) -> bool:
        try:
            self.runner.run(f"tmux has-session -t {shlex.quote(session)}")
        except subprocess.CalledProcessError:
            return False
        return True

    @staticmethod
    def _agent_command(kind: str) -> str:
        if kind == "claude":
            return "claude"
        if kind == "codex":
            return "codex"
        raise ValueError(f"Unsupported agent kind: {kind}")
