# Switchboard Telegram/Hermes Control Bridge

## Goal
Make Switchboard controllable from Telegram via Hermes by exposing a safe text-command handler and CLI entrypoint.

## Scope
- Add a parser/dispatcher for Telegram-style commands:
  - `/agents`
  - `/tasks [status]`
  - `/inbox AGENT`
  - `/send AGENT PROMPT...`
  - `/scheduler tick`
  - `/help`
- Add CLI command:
  - `switchboard telegram handle "<command text>"`
- Return short plain-text responses suitable for Telegram.
- Keep this as a Hermes bridge; no bot token, webhook, polling loop, or credentials in repo.

## Non-goals
- Dedicated Telegram bot process.
- Token storage.
- Multi-chat auth.

## Testing
- Unit tests for parser/dispatcher behavior.
- CLI tests with fake tmux for `/send` and `/scheduler tick`.
- Full test suite.

## Verification
- `switchboard telegram --help` exposes `handle`.
- All tests pass.
- Commit changes.
