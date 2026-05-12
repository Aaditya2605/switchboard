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


def make_client(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    runner = FakeRunner()
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=runner))
    service.spawn("claude", "backend", "/tmp/project", dry_run=True)
    service.spawn("codex", "reviewer", "/tmp/project", dry_run=True)
    service.create_task("Fix auth", assigned_agent="backend", priority="high", repo="~/api", due_date="2026-05-20")
    service.create_workflow("daily", agent_name="backend", prompt="Review tasks", cron="0 9 * * *")
    app = create_app(service)
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


def test_api_lists_agents_tasks_and_workflows(tmp_path):
    client, _ = make_client(tmp_path)

    agents = client.get("/api/agents").json()
    tasks = client.get("/api/tasks").json()
    workflows = client.get("/api/workflows").json()

    assert agents[0]["name"] == "backend"
    assert tasks[0]["title"] == "Fix auth"
    assert tasks[0]["priority"] == "high"
    assert workflows[0]["name"] == "daily"


def test_api_send_prompt_to_agent(tmp_path):
    client, runner = make_client(tmp_path)

    response = client.post("/api/send", json={"agent": "backend", "prompt": "Run tests"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert any("Run tests" in command for command in runner.commands)


def test_api_move_task_and_run_workflow(tmp_path):
    client, runner = make_client(tmp_path)

    moved = client.post("/api/tasks/1/move", json={"status": "completed"})
    ran = client.post("/api/workflows/daily/run")

    assert moved.status_code == 200
    assert moved.json()["status"] == "completed"
    assert ran.status_code == 200
    assert ran.json()["name"] == "daily"
    assert any("Workflow: daily" in command for command in runner.commands)
