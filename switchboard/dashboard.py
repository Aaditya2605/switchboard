from __future__ import annotations

import secrets
from dataclasses import asdict

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from switchboard.service import SwitchboardService


class ConfirmedRequest(BaseModel):
    confirm: bool = False


class SendRequest(ConfirmedRequest):
    agent: str
    prompt: str


class MoveTaskRequest(ConfirmedRequest):
    status: str


def create_app(service: SwitchboardService, auth_token: str | None = None) -> FastAPI:
    app = FastAPI(title="Switchboard Dashboard")

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

    @app.post("/api/send", dependencies=[auth])
    def api_send(request: SendRequest):
        require_confirm(request)
        service.send(request.agent, request.prompt)
        return {"ok": True}

    @app.post("/api/tasks/{task_id}/move", dependencies=[auth])
    def api_move_task(task_id: int, request: MoveTaskRequest):
        require_confirm(request)
        return asdict(service.move_task(task_id, request.status))

    @app.post("/api/workflows/{name}/run", dependencies=[auth])
    def api_run_workflow(name: str, request: ConfirmedRequest):
        require_confirm(request)
        return asdict(service.run_workflow(name))

    return app


def _render_dashboard(agents, tasks, workflows, auth_enabled: bool = False) -> str:
    agent_rows = "".join(
        f"<tr><td>{agent.name}</td><td>{agent.kind}</td><td>{agent.status}</td><td>{agent.workdir}</td></tr>"
        for agent in agents
    ) or "<tr><td colspan='4'>No agents.</td></tr>"
    task_rows = "".join(
        f"<tr><td>#{task.id}</td><td>{task.status}</td><td>{task.assigned_agent or 'unassigned'}</td>"
        f"<td>{task.priority}</td><td>{task.due_date or '-'}</td><td>{task.title}</td></tr>"
        for task in tasks
    ) or "<tr><td colspan='6'>No tasks.</td></tr>"
    workflow_rows = "".join(
        f"<tr><td>{workflow.name}</td><td>{workflow.agent_name}</td><td>{workflow.cron}</td>"
        f"<td>{'enabled' if workflow.enabled else 'disabled'}</td></tr>"
        for workflow in workflows
    ) or "<tr><td colspan='4'>No workflows.</td></tr>"
    auth_note = "Bearer-token auth enabled." if auth_enabled else "Auth disabled for local dev."
    return f"""
<!doctype html>
<html>
<head>
  <title>Switchboard</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }}
    h1, h2 {{ color: #f8fafc; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #334155; padding: .5rem; text-align: left; }}
    th {{ background: #1e293b; }}
    code {{ background: #1e293b; padding: .15rem .35rem; border-radius: .25rem; }}
  </style>
</head>
<body>
  <h1>Switchboard</h1>
  <p>Local command center for Claude Code and Codex agents. {auth_note}</p>
  <h2>Agents</h2>
  <table><thead><tr><th>Name</th><th>Kind</th><th>Status</th><th>Workdir</th></tr></thead><tbody>{agent_rows}</tbody></table>
  <h2>Tasks</h2>
  <table><thead><tr><th>ID</th><th>Status</th><th>Assignee</th><th>Priority</th><th>Due</th><th>Title</th></tr></thead><tbody>{task_rows}</tbody></table>
  <h2>Workflows</h2>
  <table><thead><tr><th>Name</th><th>Agent</th><th>Cron</th><th>State</th></tr></thead><tbody>{workflow_rows}</tbody></table>
  <h2>API</h2>
  <p>Try <code>/api/agents</code>, <code>/api/tasks</code>, and <code>/api/workflows</code>. Mutating actions require <code>confirm: true</code>.</p>
</body>
</html>
"""
