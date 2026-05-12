from __future__ import annotations

import os
import plistlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_LABEL = "com.switchboard.scheduler"


@dataclass(frozen=True)
class LaunchdResult:
    action: str
    label: str
    plist_path: Path
    commands: list[str]


@dataclass(frozen=True)
class LaunchdStatus:
    label: str
    plist_path: Path
    installed: bool


def build_scheduler_plist(label: str, repo_path: Path, switchboard_home: Path, interval: int) -> str:
    logs_dir = switchboard_home / "logs"
    program_arguments = [
        "uv",
        "run",
        "--with-editable",
        ".",
        "switchboard",
        "scheduler",
        "daemon",
        "--interval",
        str(interval),
    ]
    payload = {
        "Label": label,
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(repo_path),
        "EnvironmentVariables": {"SWITCHBOARD_HOME": str(switchboard_home)},
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(logs_dir / "scheduler.out.log"),
        "StandardErrorPath": str(logs_dir / "scheduler.err.log"),
    }
    return plistlib.dumps(payload, sort_keys=False).decode("utf-8")


class LaunchdInstaller:
    def __init__(
        self,
        repo_path: Path,
        home: Path,
        launch_agents_dir: Path,
        label: str = DEFAULT_LABEL,
        runner=subprocess.run,
    ):
        self.repo_path = repo_path
        self.home = home
        self.launch_agents_dir = launch_agents_dir
        self.label = label
        self.runner = runner

    @property
    def plist_path(self) -> Path:
        return self.launch_agents_dir / f"{self.label}.plist"

    def install(self, interval: int = 60, dry_run: bool = False) -> LaunchdResult:
        if interval <= 0:
            raise ValueError("interval must be positive")
        self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        (self.home / "logs").mkdir(parents=True, exist_ok=True)
        self.plist_path.write_text(build_scheduler_plist(self.label, self.repo_path, self.home, interval))
        commands = [
            f"launchctl bootstrap gui/{os.getuid()} {self.plist_path}",
            f"launchctl enable gui/{os.getuid()}/{self.label}",
            f"launchctl kickstart -k gui/{os.getuid()}/{self.label}",
        ]
        if not dry_run:
            for command in commands:
                self.runner(command.split(), check=True)
        return LaunchdResult(
            action="dry-run-install" if dry_run else "install",
            label=self.label,
            plist_path=self.plist_path,
            commands=[] if dry_run else commands,
        )

    def uninstall(self, dry_run: bool = False) -> LaunchdResult:
        commands = [f"launchctl bootout gui/{os.getuid()} {self.plist_path}"]
        if not dry_run:
            self.runner(commands[0].split(), check=False)
            if self.plist_path.exists():
                self.plist_path.unlink()
        return LaunchdResult(
            action="dry-run-uninstall" if dry_run else "uninstall",
            label=self.label,
            plist_path=self.plist_path,
            commands=commands,
        )

    def status(self) -> LaunchdStatus:
        return LaunchdStatus(label=self.label, plist_path=self.plist_path, installed=self.plist_path.exists())
