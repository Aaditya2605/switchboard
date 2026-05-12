from typer.testing import CliRunner

import switchboard.cli as cli
from switchboard.cli import app


runner = CliRunner()


def test_scheduler_install_launchd_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "launch_agents_dir", lambda: tmp_path / "LaunchAgents")

    result = runner.invoke(app, ["scheduler", "install-launchd", "--dry-run", "--interval", "30"])

    assert result.exit_code == 0
    assert "dry-run-install" in result.output
    assert "com.switchboard.scheduler.plist" in result.output


def test_scheduler_uninstall_launchd_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "launch_agents_dir", lambda: tmp_path / "LaunchAgents")
    assert runner.invoke(app, ["scheduler", "install-launchd", "--dry-run"]).exit_code == 0

    result = runner.invoke(app, ["scheduler", "uninstall-launchd", "--dry-run"])

    assert result.exit_code == 0
    assert "dry-run-uninstall" in result.output


def test_scheduler_launchd_status(tmp_path, monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(cli, "launch_agents_dir", lambda: tmp_path / "LaunchAgents")

    result = runner.invoke(app, ["scheduler", "launchd-status"])

    assert result.exit_code == 0
    assert "not installed" in result.output
