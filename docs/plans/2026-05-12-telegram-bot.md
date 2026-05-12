# Telegram Bot Integration

## Goal

Turn the existing safe Telegram/Hermes text-command handler into a real Telegram Bot API adapter without committing secrets.

## Scope

- Read bot token from `SWITCHBOARD_TELEGRAM_BOT_TOKEN` only.
- Optional allowlist via `SWITCHBOARD_TELEGRAM_ALLOWED_CHAT_IDS`.
- Telegram Bot API client with injectable HTTP opener for tests.
- Commands under `switchboard telegram`:
  - `poll --once --timeout N`
  - `set-webhook URL`
  - `delete-webhook`
  - `webhook-info`
- Polling should route inbound text through `handle_telegram_command` and reply via `sendMessage`.
- Unauthorized chats should get no command execution.

## Out of scope

- Committing/storing bot tokens.
- Hosting an HTTP webhook server.
- Background launchd installer for bot polling.

## Verification

- Unit tests for token loading, allowlist, polling, set/delete webhook.
- CLI tests with fake client factory.
- Full pytest suite and CLI help smoke test.
