from switchboard.db import AgentRepository, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        if "capture-pane" in command:
            return "agent output"
        return ""


def make_service(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    runner = FakeRunner()
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=runner))
    return service, runner


def test_spawn_claude_agent_records_agent_and_starts_tmux(tmp_path):
    service, runner = make_service(tmp_path)

    agent = service.spawn("claude", "backend", "/tmp/project")

    assert agent.name == "backend"
    assert agent.kind == "claude"
    assert agent.tmux_session == "switchboard-backend"
    assert any("tmux new-session" in c and "claude" in c for c in runner.commands)


def test_spawn_codex_agent_uses_codex_command(tmp_path):
    service, runner = make_service(tmp_path)

    service.spawn("codex", "reviewer", "/tmp/project")

    assert any("tmux new-session" in c and "codex" in c for c in runner.commands)


def test_send_prompt_to_agent_uses_tmux_send_keys(tmp_path):
    service, runner = make_service(tmp_path)
    service.spawn("claude", "backend", "/tmp/project")

    service.send("backend", "Run tests")

    assert any("tmux send-keys" in c and "Run tests" in c for c in runner.commands)


def test_logs_capture_pane(tmp_path):
    service, runner = make_service(tmp_path)
    service.spawn("claude", "backend", "/tmp/project")

    assert service.logs("backend") == "agent output"
    assert any("tmux capture-pane" in c for c in runner.commands)


def test_stop_agent_marks_stopped_and_kills_tmux(tmp_path):
    service, runner = make_service(tmp_path)
    service.spawn("claude", "backend", "/tmp/project")

    agent = service.stop("backend")

    assert agent.status == "stopped"
    assert any("tmux kill-session" in c for c in runner.commands)
