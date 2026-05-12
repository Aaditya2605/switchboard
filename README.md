# Switchboard

Persistent command center for Claude Code and Codex agents.

Switchboard Lite is the local MVP:

- register Claude/Codex agents
- start persistent tmux sessions
- send prompts into agents
- capture logs
- stop agents
- store agent state in SQLite
- queue agent-to-agent messages
- manage shared tasks with priority, repo, due dates, and comments
- store and run reusable workflow prompts
- run due workflow prompts with a scheduler daemon
- handle Telegram-style commands through Hermes or a real Telegram bot
- detect dead/live tmux agent sessions

## Install/dev

```bash
cd ~/projects/switchboard
uv run --with-editable . --with pytest pytest -q
```

## Commands

```bash
uv run --with-editable . switchboard init
uv run --with-editable . switchboard agents
uv run --with-editable . switchboard spawn claude backend ~/projects/myapp
uv run --with-editable . switchboard spawn codex reviewer ~/projects/myapp
uv run --with-editable . switchboard send backend "Run tests and fix failures"
uv run --with-editable . switchboard health backend
uv run --with-editable . switchboard health --all
uv run --with-editable . switchboard logs backend
uv run --with-editable . switchboard stop backend
```

Agent-to-agent comms:

```bash
uv run --with-editable . switchboard msg reviewer backend "Need the API schema"
uv run --with-editable . switchboard inbox backend
uv run --with-editable . switchboard msg reviewer backend "Need the API schema" --deliver
```

Shared task board:

```bash
uv run --with-editable . switchboard task add "Fix auth" --description "Run tests first" --agent backend --priority high --repo ~/projects/myapp --due 2026-05-20
uv run --with-editable . switchboard task list
uv run --with-editable . switchboard task update 1 --priority urgent --repo ~/projects/myapp --due 2026-05-21
uv run --with-editable . switchboard task comment 1 "Waiting on API schema" --author reviewer
uv run --with-editable . switchboard task comments 1
uv run --with-editable . switchboard task assign 1 reviewer
uv run --with-editable . switchboard task move 1 in_progress
uv run --with-editable . switchboard task move 1 completed
uv run --with-editable . switchboard task list --status completed
```

Workflow prompts:

```bash
uv run --with-editable . switchboard workflow add daily-check --agent backend --prompt "Review open tasks and suggest next action" --cron "0 9 * * *"
uv run --with-editable . switchboard workflow list
uv run --with-editable . switchboard workflow run daily-check
uv run --with-editable . switchboard workflow disable daily-check
uv run --with-editable . switchboard workflow enable daily-check
```

Scheduler:

```bash
uv run --with-editable . switchboard scheduler tick
uv run --with-editable . switchboard scheduler daemon --interval 60
uv run --with-editable . switchboard scheduler install-launchd --interval 60 --dry-run
uv run --with-editable . switchboard scheduler install-launchd --interval 60
uv run --with-editable . switchboard scheduler launchd-status
uv run --with-editable . switchboard scheduler uninstall-launchd --dry-run
```

Telegram/Hermes bridge and bot:

```bash
uv run --with-editable . switchboard telegram handle "/agents"
uv run --with-editable . switchboard telegram handle "/tasks completed"
uv run --with-editable . switchboard telegram handle "/inbox backend"
uv run --with-editable . switchboard telegram handle "/health all"
uv run --with-editable . switchboard telegram handle "/send backend Run tests"
uv run --with-editable . switchboard telegram handle "/scheduler tick"

export SWITCHBOARD_TELEGRAM_BOT_TOKEN="[REDACTED]"
export SWITCHBOARD_TELEGRAM_ALLOWED_CHAT_IDS="123456789"
uv run --with-editable . switchboard telegram poll --once --timeout 30
uv run --with-editable . switchboard telegram set-webhook https://example.com/switchboard
uv run --with-editable . switchboard telegram webhook-info
uv run --with-editable . switchboard telegram delete-webhook
```

Use `--dry-run` to register an agent without launching tmux:

```bash
uv run --with-editable . switchboard spawn claude backend ~/projects/myapp --dry-run
```

## Data

Default DB:

```txt
~/.switchboard/switchboard.db
```

Override for testing:

```bash
SWITCHBOARD_HOME=/tmp/switchboard-test uv run --with-editable . switchboard init
```

## Roadmap

- FastAPI + dashboard
