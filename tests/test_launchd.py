from pathlib import Path

from switchboard.launchd import LaunchdInstaller, build_scheduler_plist


def test_build_scheduler_plist_contains_scheduler_daemon_command(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plist = build_scheduler_plist(
        label="com.switchboard.scheduler",
        repo_path=repo,
        switchboard_home=tmp_path / "home",
        interval=45,
    )

    assert "com.switchboard.scheduler" in plist
    assert "scheduler" in plist
    assert "daemon" in plist
    assert "45" in plist
    assert str(repo) in plist
    assert "SWITCHBOARD_HOME" in plist


def test_install_launchd_dry_run_writes_plist_without_bootstrap(tmp_path):
    installer = LaunchdInstaller(
        repo_path=tmp_path / "repo",
        home=tmp_path / "switchboard-home",
        launch_agents_dir=tmp_path / "LaunchAgents",
    )

    result = installer.install(interval=60, dry_run=True)

    assert result.plist_path.exists()
    assert result.action == "dry-run-install"
    assert result.commands == []
    assert "scheduler" in result.plist_path.read_text()


def test_install_launchd_plans_bootstrap_when_not_dry_run(tmp_path):
    calls = []

    def fake_run(command, check):
        calls.append((command, check))

    installer = LaunchdInstaller(
        repo_path=tmp_path / "repo",
        home=tmp_path / "switchboard-home",
        launch_agents_dir=tmp_path / "LaunchAgents",
        runner=fake_run,
    )

    result = installer.install(interval=60, dry_run=False)

    assert any("launchctl bootstrap" in command for command in result.commands)
    assert any("launchctl enable" in command for command in result.commands)
    assert calls

def test_uninstall_launchd_dry_run_keeps_existing_plist(tmp_path):
    installer = LaunchdInstaller(
        repo_path=tmp_path / "repo",
        home=tmp_path / "switchboard-home",
        launch_agents_dir=tmp_path / "LaunchAgents",
    )
    install = installer.install(interval=60, dry_run=True)

    result = installer.uninstall(dry_run=True)

    assert install.plist_path.exists()
    assert result.action == "dry-run-uninstall"
    assert any("launchctl bootout" in command for command in result.commands)


def test_launchd_status_reports_plist_presence(tmp_path):
    installer = LaunchdInstaller(
        repo_path=tmp_path / "repo",
        home=tmp_path / "switchboard-home",
        launch_agents_dir=tmp_path / "LaunchAgents",
    )

    missing = installer.status()
    assert missing.installed is False

    installer.install(interval=60, dry_run=True)
    present = installer.status()
    assert present.installed is True
    assert present.label == "com.switchboard.scheduler"
