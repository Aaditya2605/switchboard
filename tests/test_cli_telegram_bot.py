from typer.testing import CliRunner

import switchboard.cli as cli
from switchboard.cli import app


runner = CliRunner()


class FakeBot:
    def __init__(self):
        self.calls = []

    def poll_once(self, handler, timeout=30):
        self.calls.append(("poll_once", timeout))
        response = handler("/agents")
        assert isinstance(response, str)
        return 1

    def set_webhook(self, url):
        self.calls.append(("set_webhook", url))
        return {"ok": True}

    def delete_webhook(self):
        self.calls.append(("delete_webhook",))
        return {"ok": True}

    def webhook_info(self):
        self.calls.append(("webhook_info",))
        return {"ok": True, "result": {"url": "https://example.com/hook"}}


def test_telegram_poll_once_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    fake = FakeBot()
    monkeypatch.setattr(cli, "telegram_bot", lambda: fake)

    result = runner.invoke(app, ["telegram", "poll", "--once", "--timeout", "5"])

    assert result.exit_code == 0
    assert "Handled 1 update" in result.output
    assert ("poll_once", 5) in fake.calls


def test_telegram_webhook_commands(monkeypatch):
    fake = FakeBot()
    monkeypatch.setattr(cli, "telegram_bot", lambda: fake)

    set_result = runner.invoke(app, ["telegram", "set-webhook", "https://example.com/hook"])
    info_result = runner.invoke(app, ["telegram", "webhook-info"])
    delete_result = runner.invoke(app, ["telegram", "delete-webhook"])

    assert set_result.exit_code == 0
    assert info_result.exit_code == 0
    assert delete_result.exit_code == 0
    assert "Webhook set" in set_result.output
    assert "https://example.com/hook" in info_result.output
    assert "Webhook deleted" in delete_result.output
