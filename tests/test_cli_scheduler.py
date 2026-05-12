from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "claude", "backend", "/tmp/project", "--dry-run"]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "workflow",
            "add",
            "hourly",
            "--agent",
            "backend",
            "--prompt",
            "Review tasks",
            "--cron",
            "0 * * * *",
        ],
    )
    assert result.exit_code == 0


def test_scheduler_tick_command_runs_due_workflows(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    class FakeTmux:
        def __init__(self):
            self.sent = []

        def send(self, session, prompt):
            self.sent.append((session, prompt))

    fake_tmux = FakeTmux()
    monkeypatch.setattr("switchboard.cli.TmuxClient", lambda: fake_tmux)

    result = runner.invoke(app, ["scheduler", "tick", "--now", "2026-05-12T14:00:00"])

    assert result.exit_code == 0
    assert "Ran 1 workflow" in result.output
    assert fake_tmux.sent[0][0] == "switchboard-backend"
    assert "Workflow: hourly" in fake_tmux.sent[0][1]


def test_scheduler_daemon_help_lists_options():
    result = runner.invoke(app, ["scheduler", "daemon", "--help"])

    assert result.exit_code == 0
    assert "--interval" in result.output
