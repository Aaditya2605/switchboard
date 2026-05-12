# launchd Scheduler Installer

## Goal

Let Switchboard install its scheduler daemon as a macOS LaunchAgent so workflow prompts can run automatically in the background after login.

## Scope

- Generate a LaunchAgent plist for `switchboard scheduler daemon --interval N`.
- Commands under `switchboard scheduler`:
  - `install-launchd --interval 60 [--label ...] [--dry-run]`
  - `uninstall-launchd [--label ...] [--dry-run]`
  - `launchd-status [--label ...]`
- Keep tests safe: no real `launchctl` unless user explicitly runs command without `--dry-run`.
- Store logs in `~/.switchboard/logs/`.

## Out of scope

- Linux systemd installer.
- Dedicated daemon supervisor beyond launchd.

## Verification

- Unit tests for plist generation and command planning.
- CLI tests with dry-run and monkeypatched installer path.
- Full pytest suite and CLI help smoke test.
