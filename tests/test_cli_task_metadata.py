from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["spawn", "claude", "backend", "/tmp/project", "--dry-run"]).exit_code == 0


def test_task_add_and_list_show_metadata(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "task",
            "add",
            "Fix auth",
            "--agent",
            "backend",
            "--priority",
            "high",
            "--repo",
            "~/projects/api",
            "--due",
            "2026-05-20",
        ],
    )
    assert result.exit_code == 0
    assert "high" in result.output
    assert "2026-05-20" in result.output

    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    assert "Fix auth" in result.output
    assert "high" in result.output
    assert "~/projects/api" in result.output
    assert "2026-05-20" in result.output


def test_task_update_metadata_command(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    assert runner.invoke(app, ["task", "add", "Fix auth"]).exit_code == 0

    result = runner.invoke(
        app,
        ["task", "update", "1", "--priority", "urgent", "--repo", "~/projects/api", "--due", "2026-05-21"],
    )
    assert result.exit_code == 0
    assert "urgent" in result.output
    assert "2026-05-21" in result.output


def test_task_comment_commands(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    assert runner.invoke(app, ["task", "add", "Fix auth"]).exit_code == 0

    result = runner.invoke(app, ["task", "comment", "1", "Need API schema", "--author", "aaditya"])
    assert result.exit_code == 0
    assert "Added comment" in result.output

    result = runner.invoke(app, ["task", "comments", "1"])
    assert result.exit_code == 0
    assert "aaditya" in result.output
    assert "Need API schema" in result.output
