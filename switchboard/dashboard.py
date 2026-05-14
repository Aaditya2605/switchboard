from __future__ import annotations

import secrets
from dataclasses import asdict
from html import escape
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from switchboard.db import VALID_TASK_STATUSES
from switchboard.service import SwitchboardService


class ConfirmedRequest(BaseModel):
    confirm: bool = False


class SendRequest(ConfirmedRequest):
    agent: str
    prompt: str


class MoveTaskRequest(ConfirmedRequest):
    status: str


class CreateWorkflowRequest(ConfirmedRequest):
    name: str
    agent: str
    prompt: str
    cron: str


NAV_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Core", [
        ("Search", "/search"),
        ("Overview", "/"),
        ("Agents", "/agents"),
        ("Tasks", "/tasks"),
        ("Activity", "/activity"),
    ]),
    ("Operations", [
        ("Comms", "/comms"),
        ("Approvals", "/approvals"),
        ("Workflows", "/workflows"),
        ("Logs", "/logs"),
        ("Strategy", "/strategy"),
        ("Analytics", "/analytics"),
    ]),
    ("Intelligence", [
        ("Knowledge Base", "/knowledge"),
        ("Experiments", "/experiments"),
        ("Skills", "/skills"),
    ]),
]


def create_app(service: SwitchboardService, auth_token: str | None = None) -> FastAPI:
    app = FastAPI(title="Switchboard Dashboard")
    app.state.switchboard_service = service

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        if not auth_token:
            return
        expected = f"Bearer {auth_token}"
        if authorization is None or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")

    def require_confirm(request: ConfirmedRequest) -> None:
        if not request.confirm:
            raise HTTPException(status_code=400, detail="Set confirm=true to run this action")

    auth = Depends(require_auth)
    auth_enabled = bool(auth_token)

    def layout(active_path: str, body: str, title: str = "Switchboard") -> str:
        return _render_layout(active_path, body, auth_enabled=auth_enabled, page_title=title)

    @app.get("/", response_class=HTMLResponse, dependencies=[auth])
    def home() -> str:
        return layout("/", _page_overview(service))

    @app.get("/agents", response_class=HTMLResponse, dependencies=[auth])
    def agents_page() -> str:
        return layout("/agents", _page_agents(service), title="Agents · Switchboard")

    @app.get("/tasks", response_class=HTMLResponse, dependencies=[auth])
    def tasks_page() -> str:
        return layout("/tasks", _page_tasks(service), title="Tasks · Switchboard")

    @app.get("/activity", response_class=HTMLResponse, dependencies=[auth])
    def activity_page() -> str:
        return layout("/activity", _page_activity(service), title="Activity · Switchboard")

    @app.get("/comms", response_class=HTMLResponse, dependencies=[auth])
    def comms_page() -> str:
        return layout("/comms", _page_comms(service), title="Comms · Switchboard")

    @app.get("/approvals", response_class=HTMLResponse, dependencies=[auth])
    def approvals_page() -> str:
        return layout("/approvals", _page_approvals(service), title="Approvals · Switchboard")

    @app.get("/workflows", response_class=HTMLResponse, dependencies=[auth])
    def workflows_page() -> str:
        return layout("/workflows", _page_workflows(service), title="Workflows · Switchboard")

    @app.get("/logs", response_class=HTMLResponse, dependencies=[auth])
    def logs_page() -> str:
        return layout("/logs", _page_logs(service), title="Logs · Switchboard")

    @app.get("/search", response_class=HTMLResponse, dependencies=[auth])
    def search_page(q: str = "") -> str:
        return layout("/search", _page_search(service, q), title="Search · Switchboard")

    @app.get("/strategy", response_class=HTMLResponse, dependencies=[auth])
    def strategy_page() -> str:
        return layout("/strategy", _page_strategy(service), title="Strategy · Switchboard")

    @app.get("/analytics", response_class=HTMLResponse, dependencies=[auth])
    def analytics_page() -> str:
        return layout("/analytics", _page_analytics(service), title="Analytics · Switchboard")

    @app.get("/knowledge", response_class=HTMLResponse, dependencies=[auth])
    def knowledge_page() -> str:
        return layout("/knowledge", _page_knowledge(service), title="Knowledge Base · Switchboard")

    @app.get("/experiments", response_class=HTMLResponse, dependencies=[auth])
    def experiments_page() -> str:
        return layout("/experiments", _page_experiments(service), title="Experiments · Switchboard")

    @app.get("/skills", response_class=HTMLResponse, dependencies=[auth])
    def skills_page() -> str:
        return layout("/skills", _page_skills(service), title="Skills · Switchboard")

    @app.get("/api/summary", dependencies=[auth])
    def api_summary() -> dict[str, int]:
        agents = service.list_agents()
        tasks = service.list_tasks()
        workflows = service.list_workflows()
        open_statuses = {"assigned", "in_progress", "blocked"}
        return {
            "agents": len(agents),
            "running_agents": sum(agent.status == "running" for agent in agents),
            "tasks": len(tasks),
            "open_tasks": sum(task.status in open_statuses for task in tasks),
            "workflows": len(workflows),
            "enabled_workflows": sum(workflow.enabled for workflow in workflows),
        }

    @app.get("/api/agents", dependencies=[auth])
    def api_agents():
        return [asdict(agent) for agent in service.list_agents()]

    @app.get("/api/tasks", dependencies=[auth])
    def api_tasks(status: str | None = None):
        return [asdict(task) for task in service.list_tasks(status=status)]

    @app.get("/api/workflows", dependencies=[auth])
    def api_workflows():
        return [asdict(workflow) for workflow in service.list_workflows()]

    @app.get("/api/inbox/{agent}", dependencies=[auth])
    def api_inbox(agent: str):
        return [asdict(message) for message in service.inbox(agent)]

    @app.get("/api/logs/{agent}", dependencies=[auth])
    def api_logs(agent: str, lines: int = 120):
        safe_lines = max(10, min(lines, 500))
        return {"agent": agent, "logs": service.logs(agent, lines=safe_lines), "lines": safe_lines}

    @app.post("/api/send", dependencies=[auth])
    def api_send(request: SendRequest):
        require_confirm(request)
        service.send(request.agent, request.prompt)
        return {"ok": True}

    @app.post("/api/workflows", dependencies=[auth])
    def api_create_workflow(request: CreateWorkflowRequest):
        require_confirm(request)
        return asdict(service.create_workflow(request.name, agent_name=request.agent, prompt=request.prompt, cron=request.cron))

    @app.post("/api/tasks/{task_id}/move", dependencies=[auth])
    def api_move_task(task_id: int, request: MoveTaskRequest):
        require_confirm(request)
        return asdict(service.move_task(task_id, request.status))

    @app.post("/api/workflows/{name}/run", dependencies=[auth])
    def api_run_workflow(name: str, request: ConfirmedRequest):
        require_confirm(request)
        return asdict(service.run_workflow(name))

    return app


def _h(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _js(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _status_pill(label: str, tone: str = "neutral") -> str:
    return f"<span class='pill pill-{_h(tone)}'>{_h(label)}</span>"


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _task_tone(status: str) -> str:
    return {"completed": "good", "blocked": "bad", "in_progress": "warn", "assigned": "neutral"}.get(status, "neutral")


def _priority_tone(priority: str) -> str:
    return {"urgent": "bad", "high": "warn", "normal": "neutral", "low": "muted"}.get(priority, "neutral")


def _nav_icon(label: str) -> str:
    icons = {
        "Search": "⌕",
        "Overview": "⌂",
        "Agents": "◉",
        "Tasks": "☑",
        "Activity": "↯",
        "Comms": "✉",
        "Approvals": "✓",
        "Workflows": "⚙",
        "Logs": "▤",
        "Strategy": "◇",
        "Analytics": "▦",
        "Knowledge Base": "◫",
        "Experiments": "✦",
        "Skills": "✺",
    }
    return icons.get(label, "•")


def _nav_html(active_path: str) -> str:
    parts: list[str] = []
    for group, items in NAV_GROUPS:
        parts.append(f"<div class='nav-group'><div class='nav-label'>{_h(group)}</div>")
        for label, path in items:
            cls = "nav-item active" if path == active_path else "nav-item"
            parts.append(
                f"<a class='{cls}' href='{_h(path)}'>"
                f"<span>{_nav_icon(label)}</span><span>{_h(label)}</span></a>"
            )
        parts.append("</div>")
    return "".join(parts)


def _agent_options_html(service: SwitchboardService) -> str:
    return "".join(
        f"<option value='{_h(agent.name)}'>{_h(agent.name)} · {_h(agent.kind)}</option>"
        for agent in service.list_agents()
    )


def _activity_items(service: SwitchboardService, limit: int = 8) -> list[tuple[str, str]]:
    agents = service.list_agents()
    tasks = service.list_tasks()
    workflows = service.list_workflows()
    items: list[tuple[str, str]] = []
    for task in tasks[-5:]:
        items.append(("Task", f"#{task.id} {task.title} is {task.status}"))
    for workflow in workflows[-5:]:
        items.append(("Workflow", f"{workflow.name} scheduled on {workflow.cron}"))
    for agent in agents[-5:]:
        items.append(("Agent", f"{agent.name} is {agent.status}"))
    return items[:limit]


def _activity_html(items: list[tuple[str, str]]) -> str:
    if not items:
        return "<div class='empty'>No activity yet.</div>"
    return "".join(
        f"<div class='activity'><span>{_h(kind)}</span><p>{_h(text)}</p></div>"
        for kind, text in items
    )


def _agent_rows_html(service: SwitchboardService) -> str:
    agents = service.list_agents()
    if not agents:
        return "<tr><td colspan='6' class='empty'>No agents registered yet. Spawn one with <code>switchboard spawn claude builder ~/project</code>.</td></tr>"
    return "".join(
        "<tr>"
        f"<td><div class='row-title'>{_h(agent.name)}</div><div class='row-sub'>{_h(agent.tmux_session)}</div></td>"
        f"<td>{_status_pill(agent.kind, 'agent')}</td>"
        f"<td>{_status_pill(agent.status, 'good' if agent.status == 'running' else 'bad')}</td>"
        f"<td class='mono'>{_h(agent.workdir)}</td>"
        f"<td>{_worktree_cell(agent)}</td>"
        f"<td><a class='ghost' href='/comms?agent={_h(agent.name)}'>Send prompt</a></td>"
        "</tr>"
        for agent in agents
    )


def _worktree_cell(agent) -> str:
    if not agent.worktree_path:
        return "<span class='pill pill-muted'>shared</span>"
    branch = agent.worktree_branch or "(unknown)"
    return f"<span class='pill pill-agent'>{_h(branch)}</span>"


def _task_rows_html(service: SwitchboardService) -> str:
    tasks = service.list_tasks()
    if not tasks:
        return "<tr><td colspan='7' class='empty'>No tasks yet. Add one with <code>switchboard task add</code>.</td></tr>"
    status_buttons = "".join(
        f"<button class='tiny' onclick=\"moveTask(TASK_ID,'{_js(status)}')\">{_h(status)}</button>"
        for status in VALID_TASK_STATUSES
    )
    return "".join(
        "<tr>"
        f"<td><div class='row-title'>#{task.id} {_h(task.title)}</div><div class='row-sub'>{_h(task.description or 'No description')}</div></td>"
        f"<td>{_status_pill(task.status, _task_tone(task.status))}</td>"
        f"<td>{_h(task.assigned_agent or 'unassigned')}</td>"
        f"<td>{_status_pill(task.priority, _priority_tone(task.priority))}</td>"
        f"<td class='mono'>{_h(task.repo or '—')}</td>"
        f"<td>{_h(task.due_date or '—')}</td>"
        f"<td class='actions'>{status_buttons.replace('TASK_ID', str(task.id))}</td>"
        "</tr>"
        for task in tasks
    )


def _workflow_rows_html(service: SwitchboardService) -> str:
    workflows = service.list_workflows()
    if not workflows:
        return "<tr><td colspan='6' class='empty'>No workflows. Add a cron-backed prompt from the CLI or the form below.</td></tr>"
    return "".join(
        "<tr>"
        f"<td><div class='row-title'>{_h(workflow.name)}</div><div class='row-sub'>{_h(_truncate(workflow.prompt, 92))}</div></td>"
        f"<td>{_h(workflow.agent_name)}</td>"
        f"<td class='mono'>{_h(workflow.cron)}</td>"
        f"<td>{_status_pill('enabled' if workflow.enabled else 'disabled', 'good' if workflow.enabled else 'muted')}</td>"
        f"<td class='mono'>{_h(workflow.last_run_at or 'never')}</td>"
        f"<td><button class='primary small' onclick=\"runWorkflow('{_js(workflow.name)}')\">Run now</button></td>"
        "</tr>"
        for workflow in workflows
    )


def _page_overview(service: SwitchboardService) -> str:
    agents = service.list_agents()
    tasks = service.list_tasks()
    workflows = service.list_workflows()
    running_agents = sum(agent.status == "running" for agent in agents)
    open_tasks = sum(task.status in {"assigned", "in_progress", "blocked"} for task in tasks)
    enabled_workflows = sum(workflow.enabled for workflow in workflows)
    blocked_tasks = sum(task.status == "blocked" for task in tasks)
    activity = _activity_html(_activity_items(service))

    return f"""
    <section class="hero card">
      <div>
        <p class="eyebrow">Claude Code + Codex command center</p>
        <h1>Manage agents, tasks, crons, approvals, and workflows from one local dashboard.</h1>
        <p class="muted">A lightweight control plane for persistent tmux-backed AI workers. Every nav item is a real page — bookmark what you use most.</p>
      </div>
      <div class="hero-actions">
        <a class="primary" href="/comms">Send prompt</a>
        <button class="secondary" onclick="refreshSummary()">Refresh summary</button>
      </div>
    </section>

    <section class="metrics">
      <div class="metric card"><span>Agents</span><strong>{len(agents)}</strong><small>{running_agents} running</small></div>
      <div class="metric card"><span>Tasks</span><strong>{len(tasks)}</strong><small>{open_tasks} open · {blocked_tasks} blocked</small></div>
      <div class="metric card"><span>Workflows</span><strong>{len(workflows)}</strong><small>{enabled_workflows} enabled</small></div>
      <div class="metric card"><span>Approvals</span><strong>0</strong><small>confirmation gates active</small></div>
    </section>

    <section class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Activity</p><h2>Recent activity</h2></div><a class="ghost small" href="/activity">View all</a></div>
      <div class="activity-list compact">{activity}</div>
    </section>

    <section class="grid-three">
      <a class="card mini link" href="/agents"><p class="eyebrow">Workers</p><h2>Agents →</h2><p>{len(agents)} registered · {running_agents} running.</p></a>
      <a class="card mini link" href="/tasks"><p class="eyebrow">Execution</p><h2>Tasks →</h2><p>{len(tasks)} total · {open_tasks} open · {blocked_tasks} blocked.</p></a>
      <a class="card mini link" href="/workflows"><p class="eyebrow">Operations</p><h2>Workflows →</h2><p>{len(workflows)} crons · {enabled_workflows} enabled.</p></a>
    </section>

    <section class="grid-three">
      <a class="card mini link" href="/logs"><p class="eyebrow">Logs</p><h2>Agent logs →</h2><p>Inspect recent tmux output, scrollback, and tail.</p></a>
      <a class="card mini link" href="/comms"><p class="eyebrow">Comms</p><h2>Send prompt →</h2><p>Confirmed delivery into a tmux session.</p></a>
      <a class="card mini link" href="/approvals"><p class="eyebrow">Approvals</p><h2>Gates →</h2><p>Mutations require <code>confirm: true</code>.</p></a>
    </section>
    """


def _page_agents(service: SwitchboardService) -> str:
    agents = service.list_agents()
    running = sum(agent.status == "running" for agent in agents)
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Workers</p><h1>Agents</h1><p class="muted">Claude Code and Codex sessions registered with Switchboard. Each agent owns one tmux session.</p></div>
      <div class="page-head-meta"><strong>{len(agents)}</strong><span>{running} running</span></div>
    </section>

    <section class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Registry</p><h2>Active agents</h2></div><input class="filter-input" placeholder="Filter rows..." oninput="filterTables(this.value)" /></div>
      <table><thead><tr><th>Name</th><th>Kind</th><th>Status</th><th>Workdir</th><th>Worktree</th><th>Action</th></tr></thead><tbody>{_agent_rows_html(service)}</tbody></table>
      <div class="panel-foot">
        <p>Spawn a new agent:</p>
        <pre class="code-block">switchboard spawn claude builder ~/projects/myapp
switchboard spawn codex reviewer ~/projects/myapp --worktree
switchboard worktree list</pre>
      </div>
    </section>
    """


def _page_tasks(service: SwitchboardService) -> str:
    tasks = service.list_tasks()
    open_tasks = sum(task.status in {"assigned", "in_progress", "blocked"} for task in tasks)
    blocked = sum(task.status == "blocked" for task in tasks)
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Execution</p><h1>Tasks</h1><p class="muted">Shared task board for everything assigned to agents — priority, repo, due date, and inline status moves.</p></div>
      <div class="page-head-meta"><strong>{len(tasks)}</strong><span>{open_tasks} open · {blocked} blocked</span></div>
    </section>

    <section class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Board</p><h2>All tasks</h2></div><input class="filter-input" placeholder="Filter rows..." oninput="filterTables(this.value)" /></div>
      <table><thead><tr><th>Task</th><th>Status</th><th>Assignee</th><th>Priority</th><th>Repo</th><th>Due</th><th>Move</th></tr></thead><tbody>{_task_rows_html(service)}</tbody></table>
      <div class="panel-foot">
        <p>Add or update a task from the CLI:</p>
        <pre class="code-block">switchboard task add "Fix auth" --agent backend --priority high --repo ~/projects/myapp --due 2026-05-21
switchboard task assign 1 reviewer
switchboard task move 1 completed</pre>
      </div>
    </section>
    """


def _page_activity(service: SwitchboardService) -> str:
    items = _activity_items(service, limit=40)
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Activity</p><h1>Recent activity</h1><p class="muted">Tasks, workflows, and agents in chronological order from the SQLite store.</p></div>
      <div class="page-head-meta"><strong>{len(items)}</strong><span>events</span></div>
    </section>

    <section class="card panel padded">
      <div class="activity-list">{_activity_html(items)}</div>
    </section>
    """


def _page_comms(service: SwitchboardService) -> str:
    agent_options = _agent_options_html(service)
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Comms</p><h1>Send a prompt</h1><p class="muted">Posts to <code>/api/send</code> with <code>confirm: true</code>, then injects into the agent's tmux session.</p></div>
    </section>

    <section class="card command-card">
      <div>
        <h2>Direct prompt</h2>
        <p class="muted">Choose an agent, type a task. The agent will see this as new tmux input on next idle.</p>
      </div>
      <form id="send-form" data-endpoint="/api/send" data-confirm="true" onsubmit="sendPrompt(event)">
        <select name="agent" id="agent-select">{agent_options}</select>
        <textarea name="prompt" placeholder="Ask an agent to inspect, implement, review, summarize, or run tests..." required></textarea>
        <button class="primary" type="submit">Send confirmed prompt</button>
      </form>
    </section>

    <section class="card panel padded">
      <p class="eyebrow">Agent-to-agent</p>
      <h2>Inbox messages</h2>
      <p class="muted">Use the CLI to queue messages and deliver them as prompts when convenient.</p>
      <pre class="code-block">switchboard msg reviewer backend "Need the API schema"
switchboard inbox backend
switchboard msg reviewer backend "Need the API schema" --deliver</pre>
    </section>
    """


def _page_approvals(service: SwitchboardService) -> str:
    return """
    <section class="page-head">
      <div><p class="eyebrow">Approvals</p><h1>Human gates</h1><p class="muted">Mutating API calls are blocked unless the request body explicitly includes <code>confirm: true</code>.</p></div>
    </section>

    <section class="card panel padded">
      <h2>Pending approvals</h2>
      <div class="approval-box">No pending approvals yet.</div>
      <p class="muted">Set <code>SWITCHBOARD_DASHBOARD_TOKEN</code> and run with <code>--require-token</code> to gate dashboard access behind a bearer token.</p>
    </section>
    """


def _page_workflows(service: SwitchboardService) -> str:
    workflows = service.list_workflows()
    enabled = sum(workflow.enabled for workflow in workflows)
    agent_options = _agent_options_html(service)
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Operations</p><h1>Workflows</h1><p class="muted">Cron-backed prompts. Daily triage, code review, bugfix loop, launch audit — install presets or roll your own.</p></div>
      <div class="page-head-meta"><strong>{len(workflows)}</strong><span>{enabled} enabled</span></div>
    </section>

    <section class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Schedules</p><h2>Manage Crons</h2></div><input class="filter-input" placeholder="Filter rows..." oninput="filterTables(this.value)" /></div>
      <table><thead><tr><th>Workflow</th><th>Agent</th><th>Schedule</th><th>State</th><th>Last run</th><th>Action</th></tr></thead><tbody>{_workflow_rows_html(service)}</tbody></table>
      <div class="inline-form">
        <h3>Create workflow</h3>
        <form id="workflow-form" data-endpoint="/api/workflows" data-confirm="true" onsubmit="createWorkflow(event)">
          <input name="name" placeholder="workflow-name" required />
          <select name="agent">{agent_options}</select>
          <input name="cron" placeholder="0 9 * * *" required />
          <textarea name="prompt" placeholder="Prompt to run on schedule..." required></textarea>
          <button class="primary small" type="submit">Create confirmed workflow</button>
        </form>
      </div>
      <div class="panel-foot">
        <p>Install built-in presets for an agent profile:</p>
        <pre class="code-block">switchboard workflow install-presets --agent backend --profile launch</pre>
      </div>
    </section>
    """


def _page_logs(service: SwitchboardService) -> str:
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Logs</p><h1>Agent logs</h1><p class="muted">Read recent tmux scrollback for any registered agent. Pick agent, choose line count, load.</p></div>
    </section>

    <section class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Viewer</p><h2>Tail</h2></div><button class="secondary small" onclick="loadLogs()">Load logs</button></div>
      <div class="log-controls">
        <select id="log-agent">{_agent_options_html(service)}</select>
        <input id="log-lines" type="number" min="10" max="500" value="120" />
      </div>
      <pre id="log-output" class="log-output empty">Choose an agent and load recent tmux logs.</pre>
    </section>
    """


def _page_search(service: SwitchboardService, query: str) -> str:
    q = (query or "").strip().lower()
    agents = service.list_agents()
    tasks = service.list_tasks()
    workflows = service.list_workflows()
    if q:
        matched_agents = [a for a in agents if q in a.name.lower() or q in (a.workdir or "").lower() or q in a.kind.lower()]
        matched_tasks = [t for t in tasks if q in (t.title or "").lower() or q in (t.description or "").lower() or q in (t.assigned_agent or "").lower() or q in (t.repo or "").lower()]
        matched_workflows = [w for w in workflows if q in w.name.lower() or q in (w.prompt or "").lower() or q in (w.cron or "").lower() or q in (w.agent_name or "").lower()]
    else:
        matched_agents, matched_tasks, matched_workflows = [], [], []

    def section(title: str, count: int, body: str, href: str) -> str:
        return (
            f"<section class='card panel padded'>"
            f"<div class='panel-head'><div><p class='eyebrow'>Match</p><h2>{_h(title)}</h2></div>"
            f"<a class='ghost small' href='{_h(href)}'>Open page</a></div>"
            f"<p class='muted'>{count} matching {_h(title.lower())}</p>"
            f"{body}"
            f"</section>"
        )

    agent_body = (
        "<ul class='result-list'>"
        + "".join(f"<li><strong>{_h(a.name)}</strong> <span class='muted'>{_h(a.kind)} · {_h(a.status)} · {_h(a.workdir)}</span></li>" for a in matched_agents)
        + "</ul>"
        if matched_agents else ""
    )
    task_body = (
        "<ul class='result-list'>"
        + "".join(f"<li><strong>#{t.id} {_h(t.title)}</strong> <span class='muted'>{_h(t.status)} · {_h(t.assigned_agent or 'unassigned')} · {_h(t.repo or '—')}</span></li>" for t in matched_tasks)
        + "</ul>"
        if matched_tasks else ""
    )
    workflow_body = (
        "<ul class='result-list'>"
        + "".join(f"<li><strong>{_h(w.name)}</strong> <span class='muted'>{_h(w.cron)} · {_h(w.agent_name)} · {'enabled' if w.enabled else 'disabled'}</span></li>" for w in matched_workflows)
        + "</ul>"
        if matched_workflows else ""
    )

    no_results = q and not (matched_agents or matched_tasks or matched_workflows)
    body_sections = ""
    if q:
        body_sections = (
            section("Agents", len(matched_agents), agent_body or "<p class='muted'>No matches.</p>", "/agents")
            + section("Tasks", len(matched_tasks), task_body or "<p class='muted'>No matches.</p>", "/tasks")
            + section("Workflows", len(matched_workflows), workflow_body or "<p class='muted'>No matches.</p>", "/workflows")
        )

    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Search</p><h1>Find anything</h1><p class="muted">Search names, prompts, repos, descriptions, schedules.</p></div>
    </section>

    <section class="card panel padded">
      <form method="get" action="/search" class="search-form">
        <input name="q" value="{_h(q)}" placeholder="Search agents, tasks, workflows..." autofocus />
        <button class="primary small" type="submit">Search</button>
      </form>
      {('<p class="muted">' + str(len(matched_agents) + len(matched_tasks) + len(matched_workflows)) + ' total matches for <strong>' + _h(q) + '</strong>.</p>') if q else '<p class="muted">Type to search across agents, tasks, and workflows.</p>'}
    </section>

    {body_sections if q else ''}
    {('<section class="card panel padded"><p class="muted">No matches for <strong>' + _h(q) + '</strong>.</p></section>') if no_results else ''}
    """


def _page_strategy(service: SwitchboardService) -> str:
    agents = service.list_agents()
    tasks = service.list_tasks()
    workflows = service.list_workflows()
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Strategy</p><h1>Operating rule</h1><p class="muted">A simple loop the Switchboard control plane is built around.</p></div>
    </section>

    <section class="card panel padded">
      <h2>Assign · Run · Inspect · Move</h2>
      <ol class="steps">
        <li><strong>Assign</strong> concrete work to a specific agent on the <a href="/tasks">tasks board</a>.</li>
        <li><strong>Run</strong> automation via <a href="/workflows">workflows</a> or direct prompts on <a href="/comms">comms</a>.</li>
        <li><strong>Inspect</strong> outputs in <a href="/logs">agent logs</a> and <a href="/activity">activity</a>.</li>
        <li><strong>Move</strong> tasks forward as work clears the bar.</li>
      </ol>
      <p class="muted">Right now there are {len(agents)} agents, {len(tasks)} tasks, and {len(workflows)} workflows in the loop.</p>
    </section>

    <section class="grid-three">
      <a class="card mini link" href="/workflows"><p class="eyebrow">Operations</p><h2>Install presets →</h2><p>Daily triage, code review, bugfix loop, feature build, launch audit.</p></a>
      <a class="card mini link" href="/comms"><p class="eyebrow">Comms</p><h2>Send a prompt →</h2><p>Confirmed prompts go straight into an agent's tmux session.</p></a>
      <a class="card mini link" href="/approvals"><p class="eyebrow">Approvals</p><h2>Gates →</h2><p>Mutations are blocked unless the body explicitly confirms.</p></a>
    </section>
    """


def _page_analytics(service: SwitchboardService) -> str:
    agents = service.list_agents()
    tasks = service.list_tasks()
    workflows = service.list_workflows()
    running = sum(a.status == "running" for a in agents)
    open_tasks = sum(t.status in {"assigned", "in_progress", "blocked"} for t in tasks)
    blocked = sum(t.status == "blocked" for t in tasks)
    completed = sum(t.status == "completed" for t in tasks)
    enabled_workflows = sum(w.enabled for w in workflows)
    repos = {(t.repo or "—") for t in tasks if t.repo}
    return f"""
    <section class="page-head">
      <div><p class="eyebrow">Analytics</p><h1>Signal</h1><p class="muted">Counts pulled straight from SQLite. No external telemetry.</p></div>
    </section>

    <section class="metrics">
      <div class="metric card"><span>Agents</span><strong>{len(agents)}</strong><small>{running} running</small></div>
      <div class="metric card"><span>Open tasks</span><strong>{open_tasks}</strong><small>{blocked} blocked</small></div>
      <div class="metric card"><span>Completed</span><strong>{completed}</strong><small>this DB</small></div>
      <div class="metric card"><span>Workflows</span><strong>{len(workflows)}</strong><small>{enabled_workflows} enabled</small></div>
    </section>

    <section class="card panel padded">
      <h2>Active repos</h2>
      <p class="muted">{len(repos)} repos referenced by tasks.</p>
      <ul class="result-list">
        {''.join('<li><span class="mono">' + _h(r) + '</span></li>' for r in sorted(repos)) or '<li class="muted">No repos tagged yet — pass <code>--repo</code> when creating tasks.</li>'}
      </ul>
      <p class="muted">Programmatic access: <code>GET /api/summary</code>, <code>GET /api/agents</code>, <code>GET /api/tasks</code>, <code>GET /api/workflows</code>.</p>
    </section>
    """


def _page_knowledge(service: SwitchboardService) -> str:
    return """
    <section class="page-head">
      <div><p class="eyebrow">Knowledge Base</p><h1>Local-first context</h1><p class="muted">Switchboard's data lives next to your code. Connect repo context, prompts, and notes via workflows.</p></div>
    </section>

    <section class="card panel padded">
      <h2>Where things live</h2>
      <ul class="result-list">
        <li><strong>Default DB</strong> <span class="mono">~/.switchboard/switchboard.db</span></li>
        <li><strong>Override</strong> set <code>SWITCHBOARD_HOME</code> for an isolated install</li>
        <li><strong>Logs</strong> tmux scrollback for each agent</li>
        <li><strong>Presets</strong> <code>switchboard/presets.py</code> — workflow profiles shipped with Switchboard</li>
      </ul>
    </section>

    <section class="card panel padded">
      <h2>Feed an agent context</h2>
      <p class="muted">Prompts can reference repo paths, docs, or other agents' outputs. Switchboard does not embed or vectorize — it relays.</p>
      <pre class="code-block">switchboard send backend "Read docs/SECURITY.md and propose three threats we haven't documented"
switchboard workflow add weekly-summary --agent backend --prompt "Summarize this week's commits" --cron "0 18 * * 5"</pre>
    </section>
    """


def _page_experiments(service: SwitchboardService) -> str:
    return """
    <section class="page-head">
      <div><p class="eyebrow">Experiments</p><h1>Sandbox</h1><p class="muted">Try changes safely before turning them on for real agents.</p></div>
    </section>

    <section class="card panel padded">
      <h2>Dry runs</h2>
      <p class="muted">Register agents without launching tmux to script through state changes safely.</p>
      <pre class="code-block">switchboard spawn claude builder ~/projects/myapp --dry-run
switchboard scheduler install-launchd --interval 60 --dry-run
switchboard scheduler tick</pre>
    </section>

    <section class="card panel padded">
      <h2>Review/fix loop</h2>
      <p class="muted">Pair a Claude builder agent with a Codex reviewer and run them against each other through workflows.</p>
      <pre class="code-block">switchboard workflow install-presets --agent reviewer --profile launch
switchboard workflow run code-review
switchboard workflow run bugfix-loop</pre>
    </section>
    """


def _page_skills(service: SwitchboardService) -> str:
    return """
    <section class="page-head">
      <div><p class="eyebrow">Skills</p><h1>Capabilities</h1><p class="muted">What Switchboard can do out of the box.</p></div>
    </section>

    <section class="grid-three">
      <div class="card mini"><p class="eyebrow">Agents</p><h2>Persistent sessions</h2><p>tmux-backed Claude Code and Codex with health checks and dry-run spawn.</p></div>
      <div class="card mini"><p class="eyebrow">Tasks</p><h2>Shared board</h2><p>Priority, repo, due dates, comments, status moves — usable from CLI or dashboard.</p></div>
      <div class="card mini"><p class="eyebrow">Workflows</p><h2>Cron prompts</h2><p>Schedule prompts. Built-in presets cover daily triage, code review, launch audit.</p></div>
      <div class="card mini"><p class="eyebrow">Scheduler</p><h2>launchd daemon</h2><p>macOS install/uninstall scripts. Dry-run friendly. systemd is on the roadmap.</p></div>
      <div class="card mini"><p class="eyebrow">Telegram</p><h2>Remote control</h2><p>Hermes-style commands plus a real Telegram bot with allowed-chat list.</p></div>
      <div class="card mini"><p class="eyebrow">API</p><h2>Local HTTP</h2><p><code>/api/agents</code> <code>/api/tasks</code> <code>/api/workflows</code> <code>/api/summary</code></p></div>
    </section>
    """


def _render_layout(active_path: str, body: str, auth_enabled: bool, page_title: str) -> str:
    auth_note = "Bearer-token auth enabled" if auth_enabled else "Auth disabled for local dev"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_h(page_title)}</title>
  <style>{_dashboard_css()}</style>
</head>
<body>
  <aside class="sidebar">
    <a class="brand" href="/"><div class="logo">S</div><div><strong>Switchboard</strong><span>agent ops</span></div></a>
    {_nav_html(active_path)}
    <div class="side-card">
      <span class="dot"></span>{_h(auth_note)}<br><small>Mutations require <code>confirm: true</code></small>
      <div class="live-toggle">
        <button id="live-toggle" type="button" onclick="toggleLive()" aria-pressed="false">Live: off</button>
        <small>Poll <code>/api/summary</code> every 10s and reload on change.</small>
      </div>
    </div>
  </aside>

  <main class="shell">
    {body}
  </main>

  <div id="toast" role="status"></div>
  <script>{_dashboard_js()}</script>
</body>
</html>"""


def _dashboard_css() -> str:
    return """
:root{--bg:#f6f4ef;--sidebar:#eeebe3;--card:#fffdf8;--text:#1f2933;--muted:#737067;--line:#ded9cc;--yellow:#f5c542;--yellow-soft:#fff3bf;--red:#e5484d;--green:#2f9e44;--blue:#2563eb;--shadow:0 18px 50px rgba(31,41,51,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:14px}
.sidebar{position:fixed;inset:0 auto 0 0;width:255px;background:var(--sidebar);border-right:1px solid var(--line);padding:20px 14px;overflow:auto}
.brand{display:flex;gap:12px;align-items:center;margin:2px 8px 22px;text-decoration:none;color:inherit}
.logo{width:34px;height:34px;border-radius:10px;background:var(--yellow);display:grid;place-items:center;font-weight:900;box-shadow:inset 0 0 0 1px rgba(0,0,0,.1)}
.brand strong{display:block;font-size:15px}.brand span,.muted,.row-sub,.metric small,.toolbar span{color:var(--muted)}
.nav-group{margin:16px 0}.nav-label{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#918b7c;margin:0 10px 8px}
.nav-item{display:flex;align-items:center;gap:10px;color:#423f37;text-decoration:none;padding:9px 10px;border-radius:10px;margin:2px 0}
.nav-item:hover{background:#f8f3df;color:#17130a}
.nav-item.active{background:var(--yellow-soft);color:#17130a;font-weight:650}
.side-card{margin:20px 8px;padding:12px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.45);color:var(--muted);line-height:1.55}
.live-toggle{margin-top:10px;display:flex;flex-direction:column;gap:6px}
.live-toggle button{width:100%;padding:7px 10px;border:1px solid var(--line);border-radius:10px;background:white;font:inherit;cursor:pointer;color:#3a382f;font-weight:650}
.live-toggle button[aria-pressed="true"]{background:#e8f7ec;border-color:#bfe6c5;color:#1d7f36}
.live-toggle small{color:var(--muted);font-size:11px;line-height:1.4}
.dot{display:inline-block;width:8px;height:8px;border-radius:999px;background:var(--green);margin-right:7px}
.shell{margin-left:255px;padding:28px;max-width:1450px}
.card{background:var(--card);border:1px solid var(--line);border-radius:22px;box-shadow:var(--shadow)}
.hero{display:flex;justify-content:space-between;gap:22px;padding:28px 30px;align-items:flex-start;margin-bottom:16px}
.eyebrow{margin:0 0 8px;text-transform:uppercase;letter-spacing:.1em;color:#9b7a10;font-size:11px;font-weight:800}
.hero h1{max-width:820px;font-size:34px;line-height:1.05;margin:0 0 12px;letter-spacing:-.04em}.hero p{max-width:760px;line-height:1.55}
.hero-actions{display:flex;gap:10px;white-space:nowrap}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;padding:6px 4px 18px}
.page-head h1{margin:6px 0 6px;font-size:30px;letter-spacing:-.04em}
.page-head p{margin:0;max-width:720px;line-height:1.55}
.page-head-meta{text-align:right}
.page-head-meta strong{display:block;font-size:30px;letter-spacing:-.04em}
.page-head-meta span{color:var(--muted)}
.metrics,.grid-three{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 16px}
.grid-three{grid-template-columns:repeat(3,1fr)}
.grid-two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:0 0 16px}
.metric{padding:18px}.metric span{color:var(--muted);display:block}.metric strong{display:block;font-size:31px;letter-spacing:-.04em;margin:8px 0 4px}
.toolbar{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;margin-bottom:16px}.toolbar div span{display:block;margin-top:4px}
.toolbar input{width:min(520px,48vw);padding:12px 14px;border:1px solid var(--line);border-radius:14px;background:white}
.command-card{display:grid;grid-template-columns:330px 1fr;gap:20px;padding:20px;margin-bottom:16px}
.command-card h2,.panel h2,.mini h2{margin:0 0 8px;font-size:20px;letter-spacing:-.02em}
.command-card form{display:grid;gap:10px}
.command-card select,.command-card textarea{border:1px solid var(--line);border-radius:14px;background:white;padding:12px;font:inherit}
.command-card textarea{min-height:86px;resize:vertical}
.panel{padding:0;margin-bottom:16px;overflow:hidden}
.panel.padded{padding:20px 22px}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:20px 22px 12px}
.panel-head h2{margin:0 0 4px}
.panel-head .filter-input{padding:9px 12px;border:1px solid var(--line);border-radius:12px;background:white;font:inherit;min-width:200px}
.panel-head span{color:var(--muted)}.panel h3{padding:0 22px;margin:0 0 10px;font-size:15px;color:#5e5a50}
.panel-foot{padding:14px 22px 22px;border-top:1px dashed var(--line);background:#faf8f1}
.panel-foot p{margin:0 0 10px;color:var(--muted)}
.code-block{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;background:#fffdf6;border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:0;white-space:pre-wrap;color:#3a382f;overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#8b8578;background:#faf8f1;text-align:left;padding:11px 14px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
td{padding:13px 14px;border-bottom:1px solid #ebe6da;vertical-align:middle}tr:last-child td{border-bottom:0}
.row-title{font-weight:700}.mono{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;color:#59564e}
.pill{display:inline-flex;align-items:center;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:700;border:1px solid transparent;background:#f1eee5;color:#514d43}
.pill-good{background:#e8f7ec;color:#1d7f36}.pill-bad{background:#ffe8e8;color:#b4232a}.pill-warn{background:#fff2cf;color:#936700}
.pill-agent{background:#e9f0ff;color:#174ea6}.pill-muted{background:#efefef;color:#777}
.inline-form{padding:6px 22px 22px}
.inline-form h3{padding:0;margin:0 0 10px;font-size:15px;color:#5e5a50}
.inline-form form{display:grid;grid-template-columns:1fr 1fr 1fr 2fr auto;gap:10px;align-items:center}
.inline-form input,.inline-form select,.inline-form textarea{border:1px solid var(--line);border-radius:14px;background:white;padding:10px 12px;font:inherit}
.inline-form textarea{min-height:42px;resize:vertical}
.search-form{display:flex;gap:10px;align-items:center;margin-bottom:10px}
.search-form input{flex:1;padding:12px 14px;border:1px solid var(--line);border-radius:14px;background:white;font:inherit}
.log-controls{display:flex;gap:10px;padding:0 22px 14px}
.log-controls select,.log-controls input{border:1px solid var(--line);border-radius:14px;background:white;padding:10px 12px;font:inherit}
.log-controls input{width:120px}
.log-output{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;margin:0 22px 22px;padding:14px;background:#faf8f1;border:1px solid var(--line);border-radius:14px;white-space:pre-wrap;color:#3a382f;min-height:48px}
.log-output.empty{font-family:inherit;color:var(--muted)}
.actions{min-width:245px}
.tiny,.ghost,.primary,.secondary{border:0;border-radius:12px;padding:9px 12px;font-weight:750;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center}
.tiny{font-size:11px;margin:2px;background:#f3f0e8;color:#514d43}
.ghost{background:#f3f0e8;color:#37342d}
.ghost.small{padding:7px 10px;font-size:12px}
.primary{background:#1e293b;color:white}.primary.small{padding:8px 11px;font-size:12px}
.secondary{background:var(--yellow-soft);color:#523d00}.secondary.small{padding:8px 11px;font-size:12px}
.mini{padding:18px;min-height:140px}.mini p{line-height:1.55}
.card.link{text-decoration:none;color:inherit;transition:transform .08s ease, box-shadow .15s ease;display:block}
.card.link:hover{transform:translateY(-1px);box-shadow:0 22px 60px rgba(31,41,51,.12)}
.activity-list{display:grid;gap:10px}
.activity-list.compact{padding:0 22px 18px}
.activity{border:1px solid var(--line);border-radius:14px;padding:10px 12px;background:#fffaf0}
.activity span{font-size:11px;color:#9b7a10;text-transform:uppercase;font-weight:800}.activity p{margin:4px 0 0}
.approval-box,.empty{padding:16px;border:1px dashed var(--line);border-radius:14px;background:#fbf8ef;color:var(--muted)}
.result-list{margin:0;padding:0;list-style:none;display:grid;gap:8px}
.result-list li{padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:#fffaf0}
.steps{margin:8px 0 0;padding-left:20px}.steps li{margin:6px 0;line-height:1.6}
#toast{position:fixed;right:22px;bottom:22px;max-width:360px;background:#111827;color:white;padding:12px 14px;border-radius:14px;box-shadow:var(--shadow);opacity:0;transform:translateY(10px);transition:.2s}#toast.show{opacity:1;transform:translateY(0)}
code{background:#f1eee5;border:1px solid #e2ddd0;border-radius:7px;padding:1px 5px;font-family:"SFMono-Regular",Consolas,monospace;font-size:12px}
@media(max-width:960px){.sidebar{position:static;width:auto;height:auto}.shell{margin-left:0;padding:16px}.hero,.command-card,.grid-two,.page-head{grid-template-columns:1fr;display:grid}.metrics,.grid-three{grid-template-columns:1fr 1fr}.hero-actions{white-space:normal}.toolbar{display:grid;gap:12px}.toolbar input{width:100%}.inline-form form{grid-template-columns:1fr}}
@media(max-width:640px){.metrics,.grid-three{grid-template-columns:1fr}table{font-size:12px}.actions{min-width:160px}.hero h1{font-size:26px}.page-head h1{font-size:24px}}
"""


def _dashboard_js() -> str:
    return """
function toast(message){const el=document.getElementById('toast');el.textContent=message;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2600)}
async function postJSON(url,payload){const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,confirm:true})});if(!res.ok){throw new Error(await res.text())}return res.json()}
async function sendPrompt(event){event.preventDefault();const form=event.currentTarget;const agent=form.agent.value;const prompt=form.prompt.value.trim();if(!prompt)return;try{await postJSON('/api/send',{agent,prompt});form.prompt.value='';toast(`Sent prompt to ${agent}`)}catch(err){toast(`Send failed: ${err.message}`)}}
async function runWorkflow(name){try{await postJSON(`/api/workflows/${encodeURIComponent(name)}/run`,{});toast(`Ran workflow: ${name}`);setTimeout(()=>location.reload(),700)}catch(err){toast(`Workflow failed: ${err.message}`)}}
async function moveTask(id,status){try{await postJSON(`/api/tasks/${id}/move`,{status});toast(`Moved task #${id} to ${status}`);setTimeout(()=>location.reload(),500)}catch(err){toast(`Move failed: ${err.message}`)}}
async function createWorkflow(event){event.preventDefault();const form=event.currentTarget;const payload={name:form.name.value.trim(),agent:form.agent.value,cron:form.cron.value.trim(),prompt:form.prompt.value.trim()};if(!payload.name||!payload.prompt||!payload.cron)return;try{await postJSON('/api/workflows',payload);toast(`Created workflow: ${payload.name}`);setTimeout(()=>location.reload(),700)}catch(err){toast(`Create failed: ${err.message}`)}}
async function loadLogs(){const agent=document.getElementById('log-agent').value;const lines=document.getElementById('log-lines').value||120;const out=document.getElementById('log-output');try{const data=await fetch(`/api/logs/${encodeURIComponent(agent)}?lines=${encodeURIComponent(lines)}`).then(r=>{if(!r.ok)throw new Error(r.statusText);return r.json()});out.classList.remove('empty');out.textContent=data.logs||'(no logs)';toast(`Loaded logs for ${agent}`)}catch(err){out.textContent=`Failed to load logs: ${err.message}`;toast(`Logs failed: ${err.message}`)}}
function filterTables(query){const q=(query||'').toLowerCase();document.querySelectorAll('tbody tr').forEach(row=>{row.style.display=row.innerText.toLowerCase().includes(q)?'':'none'})}
async function refreshSummary(){try{const data=await fetch('/api/summary').then(r=>r.json());toast(`${data.agents} agents · ${data.tasks} tasks · ${data.workflows} workflows`)}catch(err){toast(`Refresh failed: ${err.message}`)}}
const LIVE_KEY='switchboard.live';
let __liveTimer=null;
let __liveHash=null;
async function pollLive(){try{const data=await fetch('/api/summary',{cache:'no-cache'}).then(r=>r.json());const hash=JSON.stringify(data);if(__liveHash!==null&&__liveHash!==hash){location.reload();return}__liveHash=hash}catch{}}
function setLiveEnabled(enabled){const btn=document.getElementById('live-toggle');if(btn){btn.setAttribute('aria-pressed',String(enabled));btn.textContent=`Live: ${enabled?'on':'off'}`}if(__liveTimer){clearInterval(__liveTimer);__liveTimer=null}if(enabled){__liveHash=null;pollLive();__liveTimer=setInterval(pollLive,10000)}localStorage.setItem(LIVE_KEY,enabled?'1':'0')}
function toggleLive(){setLiveEnabled(localStorage.getItem(LIVE_KEY)!=='1')}
document.addEventListener('DOMContentLoaded',()=>{setLiveEnabled(localStorage.getItem(LIVE_KEY)==='1')});
"""
