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

    @app.get("/", response_class=HTMLResponse, dependencies=[auth])
    def home() -> str:
        agents = service.list_agents()
        tasks = service.list_tasks()
        workflows = service.list_workflows()
        return _render_dashboard(agents, tasks, workflows, auth_enabled=bool(auth_token))

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


def _status_pill(label: str, tone: str = "neutral") -> str:
    return f"<span class='pill pill-{_h(tone)}'>{_h(label)}</span>"


def _render_dashboard(agents, tasks, workflows, auth_enabled: bool = False) -> str:
    auth_note = "Bearer-token auth enabled" if auth_enabled else "Auth disabled for local dev"
    running_agents = sum(agent.status == "running" for agent in agents)
    open_tasks = sum(task.status in {"assigned", "in_progress", "blocked"} for task in tasks)
    enabled_workflows = sum(workflow.enabled for workflow in workflows)
    blocked_tasks = sum(task.status == "blocked" for task in tasks)

    nav_groups = [
        ("Core", ["Search", "Overview", "Agents", "Tasks", "Activity"]),
        ("Operations", ["Comms", "Approvals", "Workflows", "Logs", "Strategy", "Analytics"]),
        ("Intelligence", ["Knowledge Base", "Experiments", "Skills"]),
    ]
    nav_html = "".join(
        f"<div class='nav-group'><div class='nav-label'>{_h(group)}</div>"
        + "".join(
            f"<a class='nav-item {'active' if item == 'Workflows' else ''}' href='#{_h(item.lower().replace(' ', '-'))}'>"
            f"<span>{_nav_icon(item)}</span><span>{_h(item)}</span></a>"
            for item in items
        )
        + "</div>"
        for group, items in nav_groups
    )

    agent_options = "".join(f"<option value='{_h(agent.name)}'>{_h(agent.name)} · {_h(agent.kind)}</option>" for agent in agents)

    agent_rows = "".join(
        "<tr>"
        f"<td><div class='row-title'>{_h(agent.name)}</div><div class='row-sub'>{_h(agent.tmux_session)}</div></td>"
        f"<td>{_status_pill(agent.kind, 'agent')}</td>"
        f"<td>{_status_pill(agent.status, 'good' if agent.status == 'running' else 'bad')}</td>"
        f"<td class='mono'>{_h(agent.workdir)}</td>"
        f"<td><button class='ghost' onclick=\"fillAgent('{_js(agent.name)}')\">Send prompt</button></td>"
        "</tr>"
        for agent in agents
    ) or "<tr><td colspan='5' class='empty'>No agents registered yet. Spawn one from the CLI.</td></tr>"

    status_buttons = "".join(f"<button class='tiny' onclick=\"moveTask(TASK_ID,'{_js(status)}')\">{_h(status)}</button>" for status in VALID_TASK_STATUSES)
    task_rows = "".join(
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
    ) or "<tr><td colspan='7' class='empty'>No tasks yet. Add one with switchboard task add.</td></tr>"

    workflow_rows = "".join(
        "<tr>"
        f"<td><div class='row-title'>{_h(workflow.name)}</div><div class='row-sub'>{_h(_truncate(workflow.prompt, 92))}</div></td>"
        f"<td>{_h(workflow.agent_name)}</td>"
        f"<td class='mono'>{_h(workflow.cron)}</td>"
        f"<td>{_status_pill('enabled' if workflow.enabled else 'disabled', 'good' if workflow.enabled else 'muted')}</td>"
        f"<td class='mono'>{_h(workflow.last_run_at or 'never')}</td>"
        f"<td><button class='primary small' onclick=\"runWorkflow('{_js(workflow.name)}')\">Run now</button></td>"
        "</tr>"
        for workflow in workflows
    ) or "<tr><td colspan='6' class='empty'>No workflows. Add a cron-backed prompt from the CLI.</td></tr>"

    activity_rows = _activity_rows(agents, tasks, workflows)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Switchboard</title>
  <style>{_dashboard_css()}</style>
</head>
<body>
  <aside class="sidebar">
    <div class="brand"><div class="logo">S</div><div><strong>Switchboard</strong><span>agent ops</span></div></div>
    {nav_html}
    <div class="side-card"><span class="dot"></span>{_h(auth_note)}<br><small>Mutations require <code>confirm: true</code></small></div>
  </aside>

  <main class="shell">
    <section id="overview" class="hero card">
      <div>
        <p class="eyebrow">Claude Code + Codex command center</p>
        <h1>Manage agents, tasks, crons, approvals, and workflows from one local dashboard.</h1>
        <p class="muted">A lightweight control plane for persistent tmux-backed AI workers. Built for local-first operation, auditability, and safe confirmed actions.</p>
      </div>
      <div class="hero-actions">
        <button class="primary" onclick="document.querySelector('#send-prompt textarea').focus()">Send prompt</button>
        <button class="secondary" onclick="refreshSummary()">Refresh summary</button>
      </div>
    </section>

    <section class="metrics">
      <div class="metric card"><span>Agents</span><strong>{len(agents)}</strong><small>{running_agents} running</small></div>
      <div class="metric card"><span>Tasks</span><strong>{len(tasks)}</strong><small>{open_tasks} open · {blocked_tasks} blocked</small></div>
      <div class="metric card"><span>Workflows</span><strong>{len(workflows)}</strong><small>{enabled_workflows} enabled</small></div>
      <div class="metric card"><span>Approvals</span><strong>0</strong><small>confirmation gates active</small></div>
    </section>

    <section id="search" class="toolbar card">
      <div><strong>Search</strong><span>Filter visible agents, tasks, and workflows.</span></div>
      <input id="table-search" placeholder="Search agents, tasks, crons, repos..." oninput="filterTables(this.value)" />
    </section>

    <section id="send-prompt" class="card command-card">
      <div>
        <p class="eyebrow">Comms</p>
        <h2>Send a prompt to an agent</h2>
        <p class="muted">Posts to <code>/api/send</code> with <code>confirm: true</code>, then injects the prompt into the agent's tmux session.</p>
      </div>
      <form id="send-form" data-endpoint="/api/send" data-confirm="true" onsubmit="sendPrompt(event)">
        <select name="agent" id="agent-select">{agent_options}</select>
        <textarea name="prompt" placeholder="Ask an agent to inspect, implement, review, summarize, or run tests..." required></textarea>
        <button class="primary" type="submit">Send confirmed prompt</button>
      </form>
    </section>

    <section id="agents" class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Workers</p><h2>Agents</h2></div><span>{len(agents)} shown</span></div>
      <table><thead><tr><th>Name</th><th>Kind</th><th>Status</th><th>Workdir</th><th>Action</th></tr></thead><tbody>{agent_rows}</tbody></table>
    </section>

    <section id="tasks" class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Execution</p><h2>Tasks</h2></div><span>{len(tasks)} shown</span></div>
      <table><thead><tr><th>Task</th><th>Status</th><th>Assignee</th><th>Priority</th><th>Repo</th><th>Due</th><th>Move</th></tr></thead><tbody>{task_rows}</tbody></table>
    </section>

    <section id="workflows" class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Operations</p><h2>Workflows</h2></div><span>{len(workflows)} crons shown</span></div>
      <h3>Manage Crons</h3>
      <table><thead><tr><th>Workflow</th><th>Agent</th><th>Schedule</th><th>State</th><th>Last run</th><th>Action</th></tr></thead><tbody>{workflow_rows}</tbody></table>
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
    </section>

    <section id="logs" class="card panel">
      <div class="panel-head"><div><p class="eyebrow">Logs</p><h2>Agent logs</h2></div><button class="secondary small" onclick="loadLogs()">Load logs</button></div>
      <div class="log-controls"><select id="log-agent">{agent_options}</select><input id="log-lines" type="number" min="10" max="500" value="120" /></div>
      <pre id="log-output" class="log-output empty">Choose an agent and load recent tmux logs.</pre>
    </section>

    <section id="approvals" class="grid-two">
      <div class="card panel"><p class="eyebrow">Approvals</p><h2>Human gates</h2><p class="muted">Mutating API actions are blocked unless the request body explicitly includes <code>confirm: true</code>.</p><div class="approval-box">No pending approvals yet.</div></div>
      <div id="activity" class="card panel"><p class="eyebrow">Activity</p><h2>Recent activity</h2><div class="activity-list">{activity_rows}</div></div>
    </section>

    <section id="strategy" class="grid-three">
      <div class="card mini"><p class="eyebrow">Strategy</p><h2>Operating rule</h2><p>Assign concrete work, run workflows, inspect outputs, then move tasks forward.</p></div>
      <div id="analytics" class="card mini"><p class="eyebrow">Analytics</p><h2>Signal</h2><p><span id="summary-json">{len(agents)} agents · {len(tasks)} tasks · {len(workflows)} workflows</span></p></div>
      <div id="knowledge-base" class="card mini"><p class="eyebrow">Knowledge Base</p><h2>Local-first</h2><p>Connect repo context and private brain data through agent prompts and workflows.</p></div>
    </section>

    <section class="grid-three">
      <div id="experiments" class="card mini"><p class="eyebrow">Experiments</p><h2>Sandbox</h2><p>Use dry-run agents, workflow subsets, and review agents before high-impact actions.</p></div>
      <div id="skills" class="card mini"><p class="eyebrow">Skills</p><h2>Capabilities</h2><p>Claude/Codex sessions, tmux delivery, task board, Telegram bridge, and cron workflows.</p></div>
      <div class="card mini"><p class="eyebrow">API</p><h2>Endpoints</h2><p><code>/api/agents</code> <code>/api/tasks</code> <code>/api/workflows</code> <code>/api/summary</code></p></div>
    </section>
  </main>

  <div id="toast" role="status"></div>
  <script>{_dashboard_js()}</script>
</body>
</html>"""


def _activity_rows(agents, tasks, workflows) -> str:
    items: list[tuple[str, str]] = []
    for task in tasks[-5:]:
        items.append(("Task", f"#{task.id} {task.title} is {task.status}"))
    for workflow in workflows[-5:]:
        items.append(("Workflow", f"{workflow.name} scheduled on {workflow.cron}"))
    for agent in agents[-5:]:
        items.append(("Agent", f"{agent.name} is {agent.status}"))
    return "".join(f"<div class='activity'><span>{_h(kind)}</span><p>{_h(text)}</p></div>" for kind, text in items[:8]) or "<div class='empty'>No activity yet.</div>"


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _task_tone(status: str) -> str:
    return {"completed": "good", "blocked": "bad", "in_progress": "warn", "assigned": "neutral"}.get(status, "neutral")


def _priority_tone(priority: str) -> str:
    return {"urgent": "bad", "high": "warn", "normal": "neutral", "low": "muted"}.get(priority, "neutral")


def _js(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _nav_icon(item: str) -> str:
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
    return icons.get(item, "•")


def _dashboard_css() -> str:
    return """
:root{--bg:#f6f4ef;--sidebar:#eeebe3;--card:#fffdf8;--text:#1f2933;--muted:#737067;--line:#ded9cc;--yellow:#f5c542;--yellow-soft:#fff3bf;--red:#e5484d;--green:#2f9e44;--blue:#2563eb;--shadow:0 18px 50px rgba(31,41,51,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:14px}.sidebar{position:fixed;inset:0 auto 0 0;width:255px;background:var(--sidebar);border-right:1px solid var(--line);padding:20px 14px;overflow:auto}.brand{display:flex;gap:12px;align-items:center;margin:2px 8px 22px}.logo{width:34px;height:34px;border-radius:10px;background:var(--yellow);display:grid;place-items:center;font-weight:900;box-shadow:inset 0 0 0 1px rgba(0,0,0,.1)}.brand strong{display:block;font-size:15px}.brand span,.muted,.row-sub,.metric small,.toolbar span{color:var(--muted)}.nav-group{margin:16px 0}.nav-label{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#918b7c;margin:0 10px 8px}.nav-item{display:flex;align-items:center;gap:10px;color:#423f37;text-decoration:none;padding:9px 10px;border-radius:10px;margin:2px 0}.nav-item:hover,.nav-item.active{background:var(--yellow-soft);color:#17130a}.side-card{margin:20px 8px;padding:12px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.45);color:var(--muted);line-height:1.55}.dot{display:inline-block;width:8px;height:8px;border-radius:999px;background:var(--green);margin-right:7px}.shell{margin-left:255px;padding:28px;max-width:1450px}.card{background:var(--card);border:1px solid var(--line);border-radius:22px;box-shadow:var(--shadow)}.hero{display:flex;justify-content:space-between;gap:22px;padding:28px 30px;align-items:flex-start}.eyebrow{margin:0 0 8px;text-transform:uppercase;letter-spacing:.1em;color:#9b7a10;font-size:11px;font-weight:800}.hero h1{max-width:820px;font-size:34px;line-height:1.05;margin:0 0 12px;letter-spacing:-.04em}.hero p{max-width:760px;line-height:1.55}.hero-actions{display:flex;gap:10px;white-space:nowrap}.metrics,.grid-three{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:16px 0}.grid-three{grid-template-columns:repeat(3,1fr)}.grid-two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0}.metric{padding:18px}.metric span{color:var(--muted);display:block}.metric strong{display:block;font-size:31px;letter-spacing:-.04em;margin:8px 0 4px}.toolbar{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;margin-bottom:16px}.toolbar div span{display:block;margin-top:4px}.toolbar input{width:min(520px,48vw);padding:12px 14px;border:1px solid var(--line);border-radius:14px;background:white}.command-card{display:grid;grid-template-columns:330px 1fr;gap:20px;padding:20px;margin-bottom:16px}.command-card h2,.panel h2,.mini h2{margin:0 0 8px;font-size:20px;letter-spacing:-.02em}.command-card form{display:grid;gap:10px}.command-card select,.command-card textarea{border:1px solid var(--line);border-radius:14px;background:white;padding:12px;font:inherit}.command-card textarea{min-height:86px;resize:vertical}.panel{padding:0;margin-bottom:16px;overflow:hidden}.panel-head{display:flex;justify-content:space-between;align-items:flex-end;padding:20px 22px 12px}.panel-head span{color:var(--muted)}.panel h3{padding:0 22px;margin:0 0 10px;font-size:15px;color:#5e5a50}table{width:100%;border-collapse:collapse}th{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#8b8578;background:#faf8f1;text-align:left;padding:11px 14px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}td{padding:13px 14px;border-bottom:1px solid #ebe6da;vertical-align:middle}tr:last-child td{border-bottom:0}.row-title{font-weight:700}.mono{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;color:#59564e}.pill{display:inline-flex;align-items:center;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:700;border:1px solid transparent;background:#f1eee5;color:#514d43}.pill-good{background:#e8f7ec;color:#1d7f36}.pill-bad{background:#ffe8e8;color:#b4232a}.pill-warn{background:#fff2cf;color:#936700}.pill-agent{background:#e9f0ff;color:#174ea6}.pill-muted{background:#efefef;color:#777}.inline-form{padding:6px 22px 22px}.inline-form h3{padding:0;margin:0 0 10px;font-size:15px;color:#5e5a50}.inline-form form{display:grid;grid-template-columns:1fr 1fr 1fr 2fr auto;gap:10px;align-items:center}.inline-form input,.inline-form select,.inline-form textarea{border:1px solid var(--line);border-radius:14px;background:white;padding:10px 12px;font:inherit}.inline-form textarea{min-height:42px;resize:vertical}.log-controls{display:flex;gap:10px;padding:0 22px 14px}.log-controls select,.log-controls input{border:1px solid var(--line);border-radius:14px;background:white;padding:10px 12px;font:inherit}.log-controls input{width:120px}.log-output{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;margin:0 22px 22px;padding:14px;background:#faf8f1;border:1px solid var(--line);border-radius:14px;white-space:pre-wrap;color:#3a382f;min-height:48px}.log-output.empty{font-family:inherit;color:var(--muted)}.actions{min-width:245px}.tiny,.ghost,.primary,.secondary{border:0;border-radius:12px;padding:9px 12px;font-weight:750;cursor:pointer}.tiny{font-size:11px;margin:2px;background:#f3f0e8;color:#514d43}.ghost{background:#f3f0e8;color:#37342d}.primary{background:#1e293b;color:white}.primary.small{padding:8px 11px;font-size:12px}.secondary{background:var(--yellow-soft);color:#523d00}.mini{padding:18px;min-height:150px}.mini p{line-height:1.55}.activity-list{display:grid;gap:10px;padding:0 0 4px}.activity{border:1px solid var(--line);border-radius:14px;padding:10px 12px;background:#fffaf0}.activity span{font-size:11px;color:#9b7a10;text-transform:uppercase;font-weight:800}.activity p{margin:4px 0 0}.approval-box,.empty{padding:16px;border:1px dashed var(--line);border-radius:14px;background:#fbf8ef;color:var(--muted)}#toast{position:fixed;right:22px;bottom:22px;max-width:360px;background:#111827;color:white;padding:12px 14px;border-radius:14px;box-shadow:var(--shadow);opacity:0;transform:translateY(10px);transition:.2s}#toast.show{opacity:1;transform:translateY(0)}code{background:#f1eee5;border:1px solid #e2ddd0;border-radius:7px;padding:1px 5px;font-family:"SFMono-Regular",Consolas,monospace;font-size:12px}@media(max-width:960px){.sidebar{position:static;width:auto;height:auto}.shell{margin-left:0;padding:16px}.hero,.command-card,.grid-two{grid-template-columns:1fr;display:grid}.metrics,.grid-three{grid-template-columns:1fr 1fr}.hero-actions{white-space:normal}.toolbar{display:grid;gap:12px}.toolbar input{width:100%}}@media(max-width:640px){.metrics,.grid-three{grid-template-columns:1fr}table{font-size:12px}.actions{min-width:160px}.hero h1{font-size:26px}}
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
function fillAgent(name){document.getElementById('agent-select').value=name;document.querySelector('#send-prompt textarea').focus();location.hash='send-prompt'}
function filterTables(query){const q=query.toLowerCase();document.querySelectorAll('tbody tr').forEach(row=>{row.style.display=row.innerText.toLowerCase().includes(q)?'':'none'})}
async function refreshSummary(){try{const data=await fetch('/api/summary').then(r=>r.json());document.getElementById('summary-json').textContent=`${data.agents} agents · ${data.tasks} tasks · ${data.workflows} workflows`;toast('Summary refreshed')}catch(err){toast(`Refresh failed: ${err.message}`)}}
"""
