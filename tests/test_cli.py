from typer.testing import CliRunner

from switchboard.cli import app


runner = CliRunner()


def test_init_command_creates_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Initialized Switchboard" in result.output
    assert (tmp_path / "switchboard.db").exists()


def test_agents_command_lists_spawned_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["spawn", "claude", "backend", "/tmp/project", "--dry-run"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["agents"])
    assert result.exit_code == 0
    assert "backend" in result.output
    assert "claude" in result.output


def test_send_command_requires_existing_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["send", "missing", "hello"])

    assert result.exit_code != 0
    assert "Unknown agent" in result.output
