from switchboard.db import AgentRepository, init_db
from switchboard.service import SwitchboardService
from switchboard.tmux import TmuxClient


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command):
        self.commands.append(command)
        return ""


def make_service(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    runner = FakeRunner()
    service = SwitchboardService(AgentRepository(db_path), TmuxClient(runner=runner))
    service.spawn("claude", "backend", "/tmp/project", dry_run=True)
    service.spawn("codex", "reviewer", "/tmp/project", dry_run=True)
    return service, runner


def test_send_agent_message_stores_message(tmp_path):
    service, _ = make_service(tmp_path)

    message = service.message("reviewer", "backend", "Need API schema")

    assert message.from_agent == "reviewer"
    assert message.to_agent == "backend"
    assert message.body == "Need API schema"
    assert message.delivered_at is None
    assert service.inbox("backend") == [message]


def test_deliver_message_injects_into_recipient_agent(tmp_path):
    service, runner = make_service(tmp_path)

    message = service.message("reviewer", "backend", "Need API schema", deliver=True)

    assert message.delivered_at is not None
    assert any("Message from reviewer" in c and "Need API schema" in c for c in runner.commands)
    assert service.inbox("backend") == []
