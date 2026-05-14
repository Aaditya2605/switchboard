from fastapi.testclient import TestClient

from switchboard.dashboard import create_app
from switchboard.db import AgentRepository, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        return ""


def make_client(tmp_path, token=None):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    runner = FakeRunner()
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=runner))
    service.spawn("claude", "backend", "/tmp/project", dry_run=True)
    service.spawn("codex", "reviewer", "/tmp/project", dry_run=True)
    service.create_task("Fix auth", assigned_agent="backend", priority="high", repo="~/api", due_date="2026-05-20")
    service.create_workflow("daily", agent_name="backend", prompt="Review tasks", cron="0 9 * * *")
    app = create_app(service, auth_token=token)
    return TestClient(app), runner


def test_dashboard_home_shows_switchboard_sections(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "Switchboard" in response.text
    assert "Agents" in response.text
    assert "Tasks" in response.text
    assert "Workflows" in response.text
    assert "backend" in response.text
    assert "Fix auth" in response.text


def test_dashboard_has_control_plane_navigation_and_actions(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    for label in [
        "Overview",
        "Agents",
        "Tasks",
        "Activity",
        "Comms",
        "Approvals",
        "Workflows",
        "Strategy",
        "Analytics",
        "Knowledge Base",
        "Experiments",
        "Skills",
        "Manage Crons",
        "Logs",
        "Create workflow",
    ]:
        assert label in response.text
    assert "data-endpoint=\"/api/send\"" in response.text
    assert "data-endpoint=\"/api/workflows\"" in response.text
    assert "data-confirm=\"true\"" in response.text
    assert "runWorkflow(" in response.text
    assert "moveTask(" in response.text
    assert "loadLogs(" in response.text


def test_dashboard_escapes_user_controlled_content(tmp_path):
    client, _ = make_client(tmp_path)
    service = client.app.state.switchboard_service
    service.create_task("<script>alert('x')</script>", assigned_agent="backend")

    response = client.get("/")

    assert "<script>alert('x')</script>" not in response.text
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in response.text


def test_api_lists_agents_tasks_and_workflows(tmp_path):
    client, _ = make_client(tmp_path)

    agents = client.get("/api/agents").json()
    tasks = client.get("/api/tasks").json()
    workflows = client.get("/api/workflows").json()

    assert agents[0]["name"] == "backend"
    assert tasks[0]["title"] == "Fix auth"
    assert tasks[0]["priority"] == "high"
    assert workflows[0]["name"] == "daily"


def test_api_summary_counts_dashboard_resources(tmp_path):
    client, _ = make_client(tmp_path)

    summary = client.get("/api/summary")

    assert summary.status_code == 200
    assert summary.json() == {
        "agents": 2,
        "running_agents": 2,
        "tasks": 1,
        "open_tasks": 1,
        "workflows": 1,
        "enabled_workflows": 1,
    }


def test_api_send_prompt_to_agent(tmp_path):
    client, runner = make_client(tmp_path)

    response = client.post("/api/send", json={"agent": "backend", "prompt": "Run tests", "confirm": True})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert any("Run tests" in command for command in runner.commands)


def test_api_move_task_and_run_workflow(tmp_path):
    client, runner = make_client(tmp_path)

    moved = client.post("/api/tasks/1/move", json={"status": "completed", "confirm": True})
    ran = client.post("/api/workflows/daily/run", json={"confirm": True})

    assert moved.status_code == 200
    assert moved.json()["status"] == "completed"
    assert ran.status_code == 200
    assert ran.json()["name"] == "daily"
    assert any("Workflow: daily" in command for command in runner.commands)


def test_api_create_workflow_and_fetch_agent_logs(tmp_path):
    client, runner = make_client(tmp_path)
    runner.commands.append("existing log line")

    created = client.post(
        "/api/workflows",
        json={"name": "launch-audit", "agent": "backend", "prompt": "Audit launch", "cron": "0 10 * * *", "confirm": True},
    )
    logs = client.get("/api/logs/backend?lines=9999")

    assert created.status_code == 200
    assert created.json()["name"] == "launch-audit"
    assert logs.status_code == 200
    assert logs.json()["agent"] == "backend"
    assert any("-S -500" in command for command in runner.commands)


def test_dashboard_requires_bearer_token_when_configured(tmp_path):
    client, _ = make_client(tmp_path, token="secret-token")

    assert client.get("/").status_code == 401
    assert client.get("/api/agents", headers={"Authorization": "Bearer wrong"}).status_code == 401

    response = client.get("/api/agents", headers={"Authorization": "Bearer secret-token"})
    assert response.status_code == 200
    assert response.json()[0]["name"] == "backend"


def test_mutating_dashboard_actions_require_confirmation(tmp_path):
    client, runner = make_client(tmp_path)

    send = client.post("/api/send", json={"agent": "backend", "prompt": "Run tests"})
    create_workflow = client.post(
        "/api/workflows",
        json={"name": "new", "agent": "backend", "prompt": "Run", "cron": "0 9 * * *"},
    )
    move = client.post("/api/tasks/1/move", json={"status": "completed"})
    run = client.post("/api/workflows/daily/run", json={})

    assert send.status_code == 400
    assert create_workflow.status_code == 400
    assert move.status_code == 400
    assert run.status_code == 400
    assert not any("Run tests" in command for command in runner.commands)
