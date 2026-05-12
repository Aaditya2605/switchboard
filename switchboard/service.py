from __future__ import annotations

import re

from switchboard.db import AgentRecord, AgentRepository
from switchboard.tmux import TmuxClient


class SwitchboardService:
    def __init__(self, agents: AgentRepository, tmux: TmuxClient):
        self.agents = agents
        self.tmux = tmux

    def spawn(self, kind: str, name: str, workdir: str, dry_run: bool = False) -> AgentRecord:
        if kind not in {"claude", "codex"}:
            raise ValueError("kind must be 'claude' or 'codex'")
        session = f"switchboard-{self._slug(name)}"
        agent = self.agents.register(name=name, kind=kind, workdir=workdir, tmux_session=session)
        if not dry_run:
            self.tmux.start_agent(session, kind, workdir)
        return agent

    def list_agents(self) -> list[AgentRecord]:
        return self.agents.list()

    def send(self, name: str, prompt: str) -> None:
        agent = self._require_agent(name)
        self.tmux.send(agent.tmux_session, prompt)
        self.agents.record_message(name, prompt, "outbound")

    def logs(self, name: str, lines: int = 120) -> str:
        agent = self._require_agent(name)
        return self.tmux.logs(agent.tmux_session, lines=lines)

    def stop(self, name: str) -> AgentRecord:
        agent = self._require_agent(name)
        self.tmux.stop(agent.tmux_session)
        return self.agents.update_status(name, "stopped")

    def _require_agent(self, name: str) -> AgentRecord:
        agent = self.agents.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name}")
        return agent

    @staticmethod
    def _slug(name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower()
        return slug or "agent"
