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


def test_overview_page_shows_brand_and_summary(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "Switchboard" in response.text
    assert "Recent activity" in response.text
    # nav-driven cross-page links rendered on overview
    assert "Agents →" in response.text
    assert "Tasks →" in response.text
    assert "Workflows →" in response.text


def test_sidebar_navigation_links_render_on_every_page(tmp_path):
    client, _ = make_client(tmp_path)
    paths = ["/", "/agents", "/tasks", "/activity", "/comms", "/approvals", "/workflows", "/logs", "/search", "/strategy", "/analytics", "/knowledge", "/experiments", "/skills"]
    nav_labels = [
        "Search",
        "Overview",
        "Agents",
        "Tasks",
        "Activity",
        "Comms",
        "Approvals",
        "Workflows",
        "Logs",
        "Strategy",
        "Analytics",
        "Knowledge Base",
        "Experiments",
        "Skills",
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
        for label in nav_labels:
            assert label in response.text, f"nav label {label!r} missing from {path}"


def test_active_nav_state_reflects_current_page(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/workflows")
    assert response.status_code == 200
    assert "class='nav-item active' href='/workflows'" in response.text
    # Other items should NOT be marked active on the workflows page
    assert "class='nav-item active' href='/agents'" not in response.text


def test_live_toggle_is_rendered_on_every_page(tmp_path):
    client, _ = make_client(tmp_path)
    for path in ["/", "/agents", "/tasks", "/workflows", "/logs", "/comms"]:
        response = client.get(path)
        assert "id=\"live-toggle\"" in response.text, f"live toggle missing from {path}"
        assert "setLiveEnabled" in response.text, f"live JS missing from {path}"


def test_agents_page_shows_agents(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/agents")

    assert response.status_code == 200
    assert "backend" in response.text
    assert "reviewer" in response.text
    assert "Active agents" in response.text


def test_tasks_page_shows_tasks(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/tasks")

    assert response.status_code == 200
    assert "Fix auth" in response.text
    assert "moveTask(" in response.text


def test_workflows_page_has_creation_form_and_actions(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/workflows")

    assert response.status_code == 200
    assert "Manage Crons" in response.text
    assert "Create workflow" in response.text
    assert "data-endpoint=\"/api/workflows\"" in response.text
    assert "data-confirm=\"true\"" in response.text
    assert "runWorkflow(" in response.text


def test_comms_page_has_send_form(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/comms")

    assert response.status_code == 200
    assert "data-endpoint=\"/api/send\"" in response.text
    assert "data-confirm=\"true\"" in response.text


def test_logs_page_has_log_viewer(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/logs")

    assert response.status_code == 200
    assert "loadLogs(" in response.text
    assert "log-output" in response.text


def test_search_page_returns_results_for_query(tmp_path):
    client, _ = make_client(tmp_path)

    empty = client.get("/search")
    assert empty.status_code == 200
    assert "Type to search" in empty.text

    response = client.get("/search?q=backend")
    assert response.status_code == 200
    assert "backend" in response.text
    # Match the agent and the workflow that uses backend
    assert "daily" in response.text


def test_tasks_page_escapes_user_controlled_content(tmp_path):
    client, _ = make_client(tmp_path)
    service = client.app.state.switchboard_service
    service.create_task("<script>alert('x')</script>", assigned_agent="backend")

    response = client.get("/tasks")

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
    assert client.get("/workflows").status_code == 401
    assert client.get("/api/agents", headers={"Authorization": "Bearer wrong"}).status_code == 401

    response = client.get("/api/agents", headers={"Authorization": "Bearer secret-token"})
    assert response.status_code == 200
    assert response.json()[0]["name"] == "backend"

    page = client.get("/agents", headers={"Authorization": "Bearer secret-token"})
    assert page.status_code == 200
    assert "backend" in page.text


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
