from __future__ import annotations

from pathlib import Path

import pytest

from switchboard.systemd import (
    DEFAULT_UNIT,
    SystemdInstaller,
    build_scheduler_unit,
)


class FakeRunner:
    def __init__(self):
        self.calls: list[list[str]] = []
        self.check_calls: list[bool] = []

    def __call__(self, cmd, check=False, **kwargs):
        self.calls.append(cmd)
        self.check_calls.append(check)
        return None


def make_installer(tmp_path) -> tuple[SystemdInstaller, FakeRunner]:
    runner = FakeRunner()
    installer = SystemdInstaller(
        repo_path=Path("/repo"),
        home=tmp_path / "home",
        units_dir=tmp_path / "units",
        unit=DEFAULT_UNIT,
        runner=runner,
    )
    return installer, runner


def test_build_scheduler_unit_contains_required_directives(tmp_path):
    unit = build_scheduler_unit(Path("/repo"), tmp_path / "home", 90)
    assert "[Service]" in unit
    assert "WorkingDirectory=/repo" in unit
    assert f"Environment=SWITCHBOARD_HOME={tmp_path / 'home'}" in unit
    assert "switchboard scheduler daemon --interval 90" in unit
    assert "WantedBy=default.target" in unit


def test_install_writes_unit_and_drives_systemctl(tmp_path):
    installer, runner = make_installer(tmp_path)
    result = installer.install(interval=120)

    assert result.action == "install"
    assert installer.unit_path.exists()
    assert (tmp_path / "home" / "logs").is_dir()
    # daemon-reload, enable, restart
    assert [cmd[:3] for cmd in runner.calls] == [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable"],
        ["systemctl", "--user", "restart"],
    ]
    assert all(check for check in runner.check_calls)


def test_install_dry_run_writes_unit_but_does_not_invoke_systemctl(tmp_path):
    installer, runner = make_installer(tmp_path)
    result = installer.install(interval=60, dry_run=True)

    assert result.action == "dry-run-install"
    assert installer.unit_path.exists()
    assert runner.calls == []
    # dry-run still reports the commands that would have run
    assert result.commands == []


def test_install_rejects_non_positive_interval(tmp_path):
    installer, _ = make_installer(tmp_path)
    with pytest.raises(ValueError):
        installer.install(interval=0)


def test_uninstall_removes_unit_and_stops_service(tmp_path):
    installer, runner = make_installer(tmp_path)
    installer.install(interval=60)
    runner.calls.clear()

    result = installer.uninstall()

    assert result.action == "uninstall"
    assert not installer.unit_path.exists()
    actions = [cmd[2] for cmd in runner.calls]
    assert actions == ["stop", "disable", "daemon-reload"]


def test_uninstall_dry_run_keeps_unit(tmp_path):
    installer, runner = make_installer(tmp_path)
    installer.install(interval=60)
    runner.calls.clear()

    result = installer.uninstall(dry_run=True)

    assert result.action == "dry-run-uninstall"
    assert installer.unit_path.exists()
    assert runner.calls == []


def test_status_reflects_unit_presence(tmp_path):
    installer, _ = make_installer(tmp_path)
    assert not installer.status().installed
    installer.install(interval=60, dry_run=True)
    assert installer.status().installed
