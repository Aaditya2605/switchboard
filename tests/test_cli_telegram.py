from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "claude", "backend", "/tmp/project", "--dry-run"]).exit_code == 0


def test_telegram_handle_agents_command(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    result = runner.invoke(app, ["telegram", "handle", "/agents"])

    assert result.exit_code == 0
    assert "backend" in result.output


def test_telegram_handle_send_command(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    class FakeTmux:
        def send(self, session, prompt):
            assert session == "switchboard-backend"
            assert prompt == "Run tests"

    monkeypatch.setattr("switchboard.cli.TmuxClient", lambda: FakeTmux())

    result = runner.invoke(app, ["telegram", "handle", "/send backend Run tests"])

    assert result.exit_code == 0
    assert "Sent" in result.output
