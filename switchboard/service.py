from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from switchboard.db import (
    VALID_TASK_PRIORITIES,
    AgentRecord,
    AgentRepository,
    MessageRecord,
    TaskCommentRecord,
    TaskRecord,
    WorkflowRecord,
    switchboard_home,
)
from switchboard.tmux import TmuxClient
from switchboard.worktrees import GitWorktrees, WorktreeError, WorktreeInfo


class SwitchboardService:
    def __init__(self, agents: AgentRepository, tmux: TmuxClient, worktrees: GitWorktrees | None = None):
        self.agents = agents
        self.tmux = tmux
        self.worktrees = worktrees or GitWorktrees()

    def spawn(
        self,
        kind: str,
        name: str,
        workdir: str,
        dry_run: bool = False,
        worktree: bool = False,
        worktree_root: str | None = None,
        branch: str | None = None,
    ) -> AgentRecord:
        if kind not in {"claude", "codex"}:
            raise ValueError("kind must be 'claude' or 'codex'")
        session = f"switchboard-{self._slug(name)}"
        final_workdir = workdir
        wt_path: str | None = None
        wt_branch: str | None = None
        if worktree:
            source = Path(workdir).expanduser().resolve()
            if worktree_root:
                target = Path(worktree_root).expanduser().resolve()
            else:
                target = (switchboard_home() / "worktrees" / self._slug(name)).resolve()
            wt_branch = branch or f"switchboard/{self._slug(name)}"
            info = self.worktrees.create(source, target, wt_branch)
            wt_path = str(info.path)
            final_workdir = wt_path
        agent = self.agents.register(
            name=name,
            kind=kind,
            workdir=final_workdir,
            tmux_session=session,
            worktree_path=wt_path,
            worktree_branch=wt_branch,
        )
        if not dry_run:
            self.tmux.start_agent(session, kind, final_workdir)
        return agent

    def prune_worktree(self, name: str, source_repo: str | None = None) -> AgentRecord:
        agent = self._require_agent(name)
        if not agent.worktree_path:
            raise ValueError(f"agent {name} has no worktree")
        target = Path(agent.worktree_path)
        source = Path(source_repo).expanduser().resolve() if source_repo else self._infer_worktree_source(target)
        try:
            self.worktrees.remove(source, target)
        except WorktreeError as exc:
            raise ValueError(str(exc)) from exc
        return self.agents.clear_worktree(name)

    def list_worktrees(self) -> list[tuple[AgentRecord, WorktreeInfo | None]]:
        out: list[tuple[AgentRecord, WorktreeInfo | None]] = []
        for agent in self.list_agents():
            if not agent.worktree_path:
                continue
            target = Path(agent.worktree_path)
            info = WorktreeInfo(path=target, branch=agent.worktree_branch or "(unknown)") if target.exists() else None
            out.append((agent, info))
        return out

    @staticmethod
    def _infer_worktree_source(target: Path) -> Path:
        # In a linked worktree, ``.git`` is a file pointing at the parent.
        marker = target / ".git"
        if marker.is_file():
            for line in marker.read_text().splitlines():
                if line.startswith("gitdir:"):
                    gitdir = Path(line.split(":", 1)[1].strip())
                    # ``gitdir`` ends with ``.git/worktrees/<name>``; the source repo lives two levels up.
                    return gitdir.parent.parent.parent
        return target

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

    def create_task(
        self,
        title: str,
        description: str = "",
        assigned_agent: str | None = None,
        priority: str = "normal",
        repo: str | None = None,
        due_date: str | None = None,
    ) -> TaskRecord:
        if assigned_agent:
            self._require_agent(assigned_agent)
        self._validate_task_metadata(priority=priority, due_date=due_date)
        return self.agents.create_task(title, description, assigned_agent, priority=priority, repo=repo, due_date=due_date)

    def list_tasks(self, status: str | None = None) -> list[TaskRecord]:
        return self.agents.list_tasks(status=status)

    def assign_task(self, task_id: int, agent_name: str) -> TaskRecord:
        self._require_agent(agent_name)
        return self.agents.assign_task(task_id, agent_name)

    def move_task(self, task_id: int, status: str) -> TaskRecord:
        return self.agents.move_task(task_id, status)

    def update_task_metadata(
        self,
        task_id: int,
        priority: str | None = None,
        repo: str | None = None,
        due_date: str | None = None,
    ) -> TaskRecord:
        self._validate_task_metadata(priority=priority, due_date=due_date)
        return self.agents.update_task_metadata(task_id, priority=priority, repo=repo, due_date=due_date)

    def add_task_comment(self, task_id: int, author: str, body: str) -> TaskCommentRecord:
        if not body.strip():
            raise ValueError("comment body cannot be empty")
        return self.agents.add_task_comment(task_id, author=author, body=body)

    def list_task_comments(self, task_id: int) -> list[TaskCommentRecord]:
        return self.agents.list_task_comments(task_id)

    def create_workflow(self, name: str, agent_name: str, prompt: str, cron: str) -> WorkflowRecord:
        self._require_agent(agent_name)
        if len(cron.split()) != 5:
            raise ValueError("cron must be a five-field expression")
        return self.agents.create_workflow(name=name, agent_name=agent_name, prompt=prompt, cron=cron)

    def list_workflows(self) -> list[WorkflowRecord]:
        return self.agents.list_workflows()

    def run_workflow(self, name: str, ran_at: str | None = None) -> WorkflowRecord:
        workflow = self.agents.get_workflow(name)
        if workflow is None:
            raise KeyError(f"Unknown workflow: {name}")
        if not workflow.enabled:
            raise ValueError(f"Workflow is disabled: {name}")
        agent = self._require_agent(workflow.agent_name)
        formatted = f"Workflow: {workflow.name}\nSchedule: {workflow.cron}\n\n{workflow.prompt}"
        self.tmux.send(agent.tmux_session, formatted)
        self.agents.record_message(agent.name, formatted, "workflow")
        return self.agents.mark_workflow_run(name, ran_at=ran_at)

    def disable_workflow(self, name: str) -> WorkflowRecord:
        return self.agents.set_workflow_enabled(name, False)

    def enable_workflow(self, name: str) -> WorkflowRecord:
        return self.agents.set_workflow_enabled(name, True)

    def health(self, name: str) -> AgentRecord:
        agent = self._require_agent(name)
        status = "running" if self.tmux.exists(agent.tmux_session) else "dead"
        return self.agents.update_status(name, status)

    def sync_health(self) -> list[AgentRecord]:
        return [self.health(agent.name) for agent in self.list_agents()]

    def _require_agent(self, name: str) -> AgentRecord:
        agent = self.agents.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name}")
        return agent

    @staticmethod
    def _validate_task_metadata(priority: str | None = None, due_date: str | None = None) -> None:
        if priority is not None and priority not in VALID_TASK_PRIORITIES:
            raise ValueError(f"Invalid task priority: {priority}")
        if due_date:
            try:
                date.fromisoformat(due_date)
            except ValueError as exc:
                raise ValueError("due date must be YYYY-MM-DD") from exc

    @staticmethod
    def _slug(name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-").lower()
        return slug or "agent"
