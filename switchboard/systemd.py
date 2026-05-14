"""systemd user-unit installer for the Switchboard scheduler.

Linux counterpart of :mod:`switchboard.launchd`. Generates a systemd user
unit at ``~/.config/systemd/user/switchboard-scheduler.service`` and drives
``systemctl --user`` to enable/start/stop it. Install/uninstall both support
``--dry-run`` to print the unit and commands without touching systemd.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_UNIT = "switchboard-scheduler.service"


@dataclass(frozen=True)
class SystemdResult:
    action: str
    unit: str
    unit_path: Path
    commands: list[str]


@dataclass(frozen=True)
class SystemdStatus:
    unit: str
    unit_path: Path
    installed: bool


def build_scheduler_unit(repo_path: Path, switchboard_home: Path, interval: int) -> str:
    logs_dir = switchboard_home / "logs"
    return (
        "[Unit]\n"
        "Description=Switchboard scheduler daemon\n"
        "After=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={repo_path}\n"
        f"Environment=SWITCHBOARD_HOME={switchboard_home}\n"
        f"ExecStart=/usr/bin/env uv run --with-editable . switchboard scheduler daemon --interval {interval}\n"
        f"StandardOutput=append:{logs_dir / 'scheduler.out.log'}\n"
        f"StandardError=append:{logs_dir / 'scheduler.err.log'}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


class SystemdInstaller:
    def __init__(
        self,
        repo_path: Path,
        home: Path,
        units_dir: Path,
        unit: str = DEFAULT_UNIT,
        runner=subprocess.run,
    ):
        self.repo_path = repo_path
        self.home = home
        self.units_dir = units_dir
        self.unit = unit
        self.runner = runner

    @property
    def unit_path(self) -> Path:
        return self.units_dir / self.unit

    def install(self, interval: int = 60, dry_run: bool = False) -> SystemdResult:
        if interval <= 0:
            raise ValueError("interval must be positive")
        self.units_dir.mkdir(parents=True, exist_ok=True)
        (self.home / "logs").mkdir(parents=True, exist_ok=True)
        self.unit_path.write_text(build_scheduler_unit(self.repo_path, self.home, interval))
        commands = [
            "systemctl --user daemon-reload",
            f"systemctl --user enable {self.unit}",
            f"systemctl --user restart {self.unit}",
        ]
        if not dry_run:
            for command in commands:
                self.runner(command.split(), check=True)
        return SystemdResult(
            action="dry-run-install" if dry_run else "install",
            unit=self.unit,
            unit_path=self.unit_path,
            commands=[] if dry_run else commands,
        )

    def uninstall(self, dry_run: bool = False) -> SystemdResult:
        commands = [
            f"systemctl --user stop {self.unit}",
            f"systemctl --user disable {self.unit}",
            "systemctl --user daemon-reload",
        ]
        if not dry_run:
            for command in commands:
                self.runner(command.split(), check=False)
            if self.unit_path.exists():
                self.unit_path.unlink()
        return SystemdResult(
            action="dry-run-uninstall" if dry_run else "uninstall",
            unit=self.unit,
            unit_path=self.unit_path,
            commands=commands,
        )

    def status(self) -> SystemdStatus:
        return SystemdStatus(unit=self.unit, unit_path=self.unit_path, installed=self.unit_path.exists())
