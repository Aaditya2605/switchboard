from __future__ import annotations

import re

from switchboard.db import AgentRecord, AgentRepository, MessageRecord, TaskRecord, WorkflowRecord
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

    def message(self, from_agent: str, to_agent: str, body: str, deliver: bool = False) -> MessageRecord:
        self._require_agent(from_agent)
        recipient = self._require_agent(to_agent)
        message = self.agents.create_message(from_agent, to_agent, body)
        if deliver:
            formatted = f"Message from {from_agent}:\n{body}"
            self.tmux.send(recipient.tmux_session, formatted)
            message = self.agents.mark_delivered(message.id)
        return message

    def inbox(self, agent_name: str) -> list[MessageRecord]:
        self._require_agent(agent_name)
        return self.agents.inbox(agent_name)

    def create_task(self, title: str, description: str = "", assigned_agent: str | None = None) -> TaskRecord:
        if assigned_agent:
            self._require_agent(assigned_agent)
        return self.agents.create_task(title, description, assigned_agent)

    def list_tasks(self, status: str | None = None) -> list[TaskRecord]:
        return self.agents.list_tasks(status=status)

    def assign_task(self, task_id: int, agent_name: str) -> TaskRecord:
        self._require_agent(agent_name)
        return self.agents.assign_task(task_id, agent_name)

    def move_task(self, task_id: int, status: str) -> TaskRecord:
        return self.agents.move_task(task_id, status)

    def create_workflow(self, name: str, agent_name: str, prompt: str, cron: str) -> WorkflowRecord:
        self._require_agent(agent_name)
        if len(cron.split()) != 5:
            raise ValueError("cron must be a five-field expression")
        return self.agents.create_workflow(name=name, agent_name=agent_name, prompt=prompt, cron=cron)

    def list_workflows(self) -> list[WorkflowRecord]:
        return self.agents.list_workflows()

    def run_workflow(self, name: str) -> WorkflowRecord:
        workflow = self.agents.get_workflow(name)
        if workflow is None:
            raise KeyError(f"Unknown workflow: {name}")
        if not workflow.enabled:
            raise ValueError(f"Workflow is disabled: {name}")
        agent = self._require_agent(workflow.agent_name)
        formatted = f"Workflow: {workflow.name}\nSchedule: {workflow.cron}\n\n{workflow.prompt}"
        self.tmux.send(agent.tmux_session, formatted)
        self.agents.record_message(agent.name, formatted, "workflow")
        return self.agents.mark_workflow_run(name)

    def disable_workflow(self, name: str) -> WorkflowRecord:
        return self.agents.set_workflow_enabled(name, False)

    def enable_workflow(self, name: str) -> WorkflowRecord:
        return self.agents.set_workflow_enabled(name, True)

    def _require_agent(self, name: str) -> AgentRecord:
        agent = self.agents.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name}")
        return agent

    @staticmethod
    def _slug(name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower()
        return slug or "agent"
