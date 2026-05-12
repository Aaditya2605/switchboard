# Switchboard Agent Health Checks

## Goal
Detect whether registered Claude/Codex tmux sessions are alive and sync agent status in SQLite.

## Scope
- Add `TmuxClient.exists(session)` using `tmux has-session`.
- Add service methods:
  - `health(name)` — check one agent and update status to `running` or `dead`.
  - `sync_health()` — check all registered agents.
- Add CLI commands:
  - `switchboard health AGENT`
  - `switchboard health --all`
- Add Telegram bridge commands:
  - `/health AGENT`
  - `/health all`
- Keep stopped agents as stopped unless their tmux session still exists, in which case status can become running.

## Tests first
- Unit tests for live/dead session detection and DB status sync.
- CLI tests with fake TmuxClient.
- Telegram handler tests.

## Verification
- Targeted tests pass.
- Full suite passes.
- CLI help exposes health command.
- Commit changes.
