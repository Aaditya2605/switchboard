from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "claude", "backend", "/tmp/project", "--dry-run"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "codex", "reviewer", "/tmp/project", "--dry-run"]).exit_code == 0


def test_msg_and_inbox_commands(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    result = runner.invoke(app, ["msg", "reviewer", "backend", "Need API schema"])
    assert result.exit_code == 0
    assert "Queued message" in result.output

    result = runner.invoke(app, ["inbox", "backend"])
    assert result.exit_code == 0
    assert "reviewer" in result.output
    assert "Need API schema" in result.output


def test_task_add_list_assign_move_commands(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    result = runner.invoke(app, ["task", "add", "Fix auth", "--description", "Run tests", "--agent", "backend"])
    assert result.exit_code == 0
    assert "Created task" in result.output

    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    assert "Fix auth" in result.output
    assert "backend" in result.output

    result = runner.invoke(app, ["task", "move", "1", "completed"])
    assert result.exit_code == 0
    assert "completed" in result.output

    result = runner.invoke(app, ["task", "list", "--status", "completed"])
    assert result.exit_code == 0
    assert "Fix auth" in result.output
