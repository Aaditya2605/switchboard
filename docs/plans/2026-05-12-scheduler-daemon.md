# Switchboard Scheduler Daemon

## Goal
Run due workflow prompts automatically from Switchboard instead of only manual `workflow run`.

## Scope
- Cron due detection for stored 5-field cron expressions.
- Scheduler service that finds enabled due workflows, dispatches them, and updates `last_run_at`.
- CLI commands:
  - `switchboard scheduler tick` — run one scheduler pass.
  - `switchboard scheduler daemon --interval N` — loop forever.
- Tests for due/not-due behavior, duplicate-run prevention, disabled workflows, and CLI smoke.

## Non-goals
- Full crontab feature parity like names, ranges, and steps.
- Background service installers / launchd / systemd.
- Telegram control.

## Implementation notes
- Keep tmux injectable for tests.
- Use UTC naive datetimes for now.
- Support `*` and exact numeric values in minute/hour/day/month/weekday fields.
- Prevent repeated dispatch within the same matching minute by checking `last_run_at`.

## Verification
- Targeted scheduler tests pass.
- Full test suite passes.
- CLI help exposes scheduler commands.
- Commit changes.
