from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "claude", "backend", "/tmp/project", "--dry-run"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "codex", "reviewer", "/tmp/project", "--dry-run"]).exit_code == 0


class FakeTmux:
    def __init__(self, live_sessions):
        self.live_sessions = set(live_sessions)

    def exists(self, session):
        return session in self.live_sessions


def test_health_command_checks_single_agent(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    monkeypatch.setattr("switchboard.cli.TmuxClient", lambda: FakeTmux({"switchboard-backend"}))

    result = runner.invoke(app, ["health", "backend"])

    assert result.exit_code == 0
    assert "backend" in result.output
    assert "running" in result.output


def test_health_command_checks_all_agents(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    monkeypatch.setattr("switchboard.cli.TmuxClient", lambda: FakeTmux({"switchboard-backend"}))

    result = runner.invoke(app, ["health", "--all"])

    assert result.exit_code == 0
    assert "backend" in result.output
    assert "running" in result.output
    assert "reviewer" in result.output
    assert "dead" in result.output
