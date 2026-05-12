import subprocess

from switchboard.db import AgentRepository, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient


class HealthRunner:
    def __init__(self, live_sessions):
        self.live_sessions = set(live_sessions)
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        if "tmux has-session" in command:
            session = command.split("-t ", 1)[1]
            if session not in self.live_sessions:
                raise subprocess.CalledProcessError(1, command)
        return ""


def make_service(tmp_path, live_sessions):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    runner = HealthRunner(live_sessions)
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=runner))
    service.spawn("claude", "backend", "/tmp/project", dry_run=True)
    service.spawn("codex", "reviewer", "/tmp/project", dry_run=True)
    return service, runner


def test_health_marks_live_agent_running(tmp_path):
    service, runner = make_service(tmp_path, live_sessions={"switchboard-backend"})

    agent = service.health("backend")

    assert agent.status == "running"
    assert any("tmux has-session" in command for command in runner.commands)


def test_health_marks_missing_tmux_session_dead(tmp_path):
    service, _ = make_service(tmp_path, live_sessions=set())

    agent = service.health("backend")

    assert agent.status == "dead"


def test_sync_health_updates_all_agents(tmp_path):
    service, _ = make_service(tmp_path, live_sessions={"switchboard-backend"})

    agents = service.sync_health()

    statuses = {agent.name: agent.status for agent in agents}
    assert statuses == {"backend": "running", "reviewer": "dead"}
