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

Agent-to-agent comms:

```bash
uv run --with-editable . switchboard msg reviewer backend "Need the API schema"
uv run --with-editable . switchboard inbox backend
uv run --with-editable . switchboard msg reviewer backend "Need the API schema" --deliver
```

Shared task board:

```bash
uv run --with-editable . switchboard task add "Fix auth" --description "Run tests first" --agent backend
uv run --with-editable . switchboard task list
uv run --with-editable . switchboard task assign 1 reviewer
uv run --with-editable . switchboard task move 1 in_progress
uv run --with-editable . switchboard task move 1 completed
uv run --with-editable . switchboard task list --status completed
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
