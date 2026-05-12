# Switchboard

Persistent command center for Claude Code and Codex agents.

Switchboard Lite is the local MVP:

- register Claude/Codex agents
- start persistent tmux sessions
- send prompts into agents
- capture logs
- stop agents
- store agent state in SQLite

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
uv run --with-editable . switchboard logs backend
uv run --with-editable . switchboard stop backend
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

- shared Kanban tasks
- agent-to-agent comms inbox
- cron/workflow prompts
- Telegram control
- FastAPI + dashboard
