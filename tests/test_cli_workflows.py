from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "claude", "backend", "/tmp/project", "--dry-run"]).exit_code == 0


def test_workflow_add_list_disable_enable_commands(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "workflow",
            "add",
            "daily-check",
            "--agent",
            "backend",
            "--prompt",
            "Review open tasks",
            "--cron",
            "0 9 * * *",
        ],
    )
    assert result.exit_code == 0
    assert "Created workflow" in result.output

    result = runner.invoke(app, ["workflow", "list"])
    assert result.exit_code == 0
    assert "daily-check" in result.output
    assert "backend" in result.output
    assert "0 9 * * *" in result.output

    result = runner.invoke(app, ["workflow", "disable", "daily-check"])
    assert result.exit_code == 0
    assert "disabled" in result.output

    result = runner.invoke(app, ["workflow", "enable", "daily-check"])
    assert result.exit_code == 0
    assert "enabled" in result.output


def test_workflow_run_command(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    add_result = runner.invoke(
        app,
        [
            "workflow",
            "add",
            "daily-check",
            "--agent",
            "backend",
            "--prompt",
            "Review open tasks",
            "--cron",
            "0 9 * * *",
        ],
    )
    assert add_result.exit_code == 0

    class FakeTmux:
        def send(self, session, prompt):
            assert session == "switchboard-backend"
            assert "Workflow: daily-check" in prompt

    monkeypatch.setattr("switchboard.cli.TmuxClient", lambda: FakeTmux())
    result = runner.invoke(app, ["workflow", "run", "daily-check"])

    assert result.exit_code == 0
    assert "Ran workflow" in result.output
