# Switchboard

**Switchboard is a local control plane for AI coding agents** — persistent Claude Code/Codex sessions, shared tasks, workflow prompts, scheduler, Telegram bridge, and a dashboard in one small Python CLI.

It is built for developers who want multiple agents working on the same repo without losing state, context, tasks, or logs.

![Switchboard dashboard overview](docs/assets/dashboard-preview.png)

## What it does

- register agents of any kind (Claude Code, Codex, Aider, plain shell, or your own — see [Agent kinds](#agent-kinds))
- spawn each agent in its own **isolated git worktree** so parallel agents don't clobber each other
- start persistent tmux sessions per agent and capture their scrollback
- send prompts into running agents, queue inter-agent messages, manage a shared task board
- **`switchboard run <task-id>`** — dispatch a task to its assigned agent's non-interactive CLI (`claude -p`, `codex exec`, …) and capture the response as a task comment
- store reusable workflow prompts, install five built-in presets (`daily-triage`, `code-review`, `bugfix-loop`, `feature-build`, `launch-audit`), run them on a cron schedule
- run the scheduler under **launchd** (macOS) or **systemd** (Linux) with one command
- handle Telegram-style commands via Hermes or a real Telegram bot
- polished multi-page web dashboard with a dedicated route per nav item: Overview, Search, Agents, Tasks, Activity, Comms, Approvals, Workflows, Logs, Strategy, Analytics, Knowledge Base, Experiments, Skills — plus a one-click **Live mode** that auto-reloads on state change

## Install

Switchboard is published on PyPI as `switchboard-agent` (the name `switchboard` was taken). The command it installs is `switchboard`.

```bash
uv tool install switchboard-agent   # or: pipx install switchboard-agent
switchboard --help
```

Runtime requirements: Python 3.11+, `tmux`, `git`, and the agent CLIs you want to drive (`claude`, `codex`, ...).

## Develop

```bash
git clone https://github.com/Aaditya2605/switchboard.git
cd switchboard
uv run --with-editable . --with pytest --with httpx pytest -q
uv run --with-editable . switchboard --help
```

Install your checkout as a local tool:

```bash
uv tool install --editable .
switchboard --help
```

## Quick demo

```bash
export SWITCHBOARD_HOME=/tmp/switchboard-demo
uv run --with-editable . switchboard init
uv run --with-editable . switchboard spawn claude builder ~/projects/myapp --dry-run
uv run --with-editable . switchboard spawn codex reviewer ~/projects/myapp --dry-run
uv run --with-editable . switchboard task add "Ship auth bugfix" --agent builder --priority high --repo ~/projects/myapp
uv run --with-editable . switchboard workflow install-presets --agent builder --profile launch
uv run --with-editable . switchboard dashboard --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

Full walkthrough: [`docs/DEMO.md`](docs/DEMO.md).

## Commands

```bash
uv run --with-editable . switchboard init
uv run --with-editable . switchboard agents
uv run --with-editable . switchboard spawn claude backend ~/projects/myapp
uv run --with-editable . switchboard spawn codex reviewer ~/projects/myapp
uv run --with-editable . switchboard send backend "Run tests and fix failures"
uv run --with-editable . switchboard health backend
uv run --with-editable . switchboard health --all
uv run --with-editable . switchboard dashboard --host 127.0.0.1 --port 8765
export SWITCHBOARD_DASHBOARD_TOKEN=replace-with-local-token
uv run --with-editable . switchboard dashboard --host 127.0.0.1 --port 8765 --require-token
uv run --with-editable . switchboard logs backend
uv run --with-editable . switchboard stop backend
```

Use `--dry-run` to register an agent without launching tmux:

```bash
uv run --with-editable . switchboard spawn claude backend ~/projects/myapp --dry-run
```

## Per-agent git worktrees

When multiple agents work on the same repo, give each one its own `git worktree` so their edits don't collide:

```bash
uv run --with-editable . switchboard spawn claude builder ~/projects/myapp --worktree
uv run --with-editable . switchboard spawn codex reviewer ~/projects/myapp --worktree --branch reviewer/wip
uv run --with-editable . switchboard worktree list
uv run --with-editable . switchboard worktree prune builder --confirm
```

The worktree lives at `$SWITCHBOARD_HOME/worktrees/<agent>` by default (override with `--worktree-root`) on a branch named `switchboard/<agent>` (override with `--branch`).

## Agent kinds

`switchboard kinds` lists the agent CLIs Switchboard knows how to launch. Out of the box: `claude`, `codex`, `aider`, and a plain interactive `shell`. Add more in two ways:

**One-off local kinds.** Drop a TOML file at `~/.switchboard/agent_kinds.toml`:

```toml
[plandex]
command = "plandex"
description = "Plandex AI engineer"

[my-claude-resume]
command = "claude --resume"
description = "Resume the most recent Claude conversation"
one_shot = ["claude", "-p", "--resume"]
```

**Shareable plugins.** Publish a Python package with an entry point:

```toml
[project.entry-points."switchboard.agent_kinds"]
gemini = "my_pkg.agents:gemini_kind"
```

```python
# my_pkg/agents.py
from switchboard.agent_kinds import AgentKind
gemini_kind = AgentKind(name="gemini", command="gemini", one_shot=("gemini", "-p"))
```

## Autonomous task dispatch

`switchboard run` sends a task's title + description (and optional repo) into its assigned agent's non-interactive CLI and stores the response as a task comment:

```bash
uv run --with-editable . switchboard task add "Audit the dashboard for accessibility issues" --agent reviewer
uv run --with-editable . switchboard run 1
uv run --with-editable . switchboard run 1 --complete   # mark done on a clean exit
uv run --with-editable . switchboard task comments 1
```

Behind the scenes Switchboard resolves the agent's kind to its `one_shot` argv prefix (`claude -p`, `codex exec`, ...) and shells out from the agent's workdir. Pair it with `--worktree` for isolated multi-agent runs against the same repo.

A real end-to-end run driving Claude *and* Codex from the same task board lives in [`docs/DOGFOOD.md`](docs/DOGFOOD.md).

### Parallel dispatch

```bash
uv run --with-editable . switchboard run-batch 1 2 3                       # specific IDs
uv run --with-editable . switchboard run-batch --status assigned --max 4   # everything still in the queue
uv run --with-editable . switchboard run-batch --status assigned --complete --max 3
```

`run-batch` dispatches multiple tasks concurrently (default `--max 3`), with per-task pass/fail so a single bad task can't tank the rest. Output is one line per task plus a summary count.

## Agent-to-agent comms

```bash
uv run --with-editable . switchboard msg reviewer backend "Need the API schema"
uv run --with-editable . switchboard inbox backend
uv run --with-editable . switchboard msg reviewer backend "Need the API schema" --deliver
```

## Shared task board

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

## Built-in workflow presets

Switchboard ships high-value presets so the system is useful immediately:

- `daily-triage`
- `code-review`
- `bugfix-loop`
- `feature-build`
- `launch-audit`

Install them:

```bash
uv run --with-editable . switchboard workflow install-presets --agent backend --profile launch
uv run --with-editable . switchboard workflow list
uv run --with-editable . switchboard workflow run code-review
```

Preset installation upserts by workflow name, so reinstalling a profile refreshes those built-in prompts and schedules.

More details: [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md).

## Custom workflow prompts

```bash
uv run --with-editable . switchboard workflow add daily-check --agent backend --prompt "Review open tasks and suggest next action" --cron "0 9 * * *"
uv run --with-editable . switchboard workflow list
uv run --with-editable . switchboard workflow run daily-check
uv run --with-editable . switchboard workflow disable daily-check
uv run --with-editable . switchboard workflow enable daily-check
```

## Scheduler

Run due workflows once, run them in a loop, or install the loop as a system service.

```bash
uv run --with-editable . switchboard scheduler tick
uv run --with-editable . switchboard scheduler daemon --interval 60
```

macOS — launchd user agent (`~/Library/LaunchAgents/com.switchboard.scheduler.plist`):

```bash
uv run --with-editable . switchboard scheduler install-launchd --interval 60 --dry-run
uv run --with-editable . switchboard scheduler install-launchd --interval 60
uv run --with-editable . switchboard scheduler launchd-status
uv run --with-editable . switchboard scheduler uninstall-launchd --dry-run
```

Linux — systemd user unit (`~/.config/systemd/user/switchboard-scheduler.service`):

```bash
uv run --with-editable . switchboard scheduler install-systemd --interval 60 --dry-run
uv run --with-editable . switchboard scheduler install-systemd --interval 60
uv run --with-editable . switchboard scheduler systemd-status
uv run --with-editable . switchboard scheduler uninstall-systemd --dry-run
```

Cron expressions support `*`, single integers, ranges (`1-5`), lists (`0,30`), and steps (`*/15`). Weekday numbering follows the cron convention (`0` and `7` = Sunday).

## Telegram/Hermes bridge and bot

```bash
uv run --with-editable . switchboard telegram handle "/agents"
uv run --with-editable . switchboard telegram handle "/tasks completed"
uv run --with-editable . switchboard telegram handle "/inbox backend"
uv run --with-editable . switchboard telegram handle "/health all"
uv run --with-editable . switchboard telegram handle "/send backend Run tests"
uv run --with-editable . switchboard telegram handle "/scheduler tick"

export SWITCHBOARD_TELEGRAM_BOT_TOKEN=replace-with-telegram-token
export SWITCHBOARD_TELEGRAM_ALLOWED_CHAT_IDS="123456789"
uv run --with-editable . switchboard telegram poll --once --timeout 30
uv run --with-editable . switchboard telegram set-webhook https://example.com/switchboard
uv run --with-editable . switchboard telegram webhook-info
uv run --with-editable . switchboard telegram delete-webhook
```

## Dashboard safety

The dashboard is a light operations control plane with sections for Overview, Agents, Tasks, Activity, Comms, Approvals, Workflows, Logs, Strategy, Analytics, Knowledge Base, Experiments, and Skills.

It includes functional controls for confirmed prompt sends, task moves, workflow creation/runs, log loading, table search, and summary refresh.

Set `SWITCHBOARD_DASHBOARD_TOKEN` to require bearer auth on dashboard and API requests.
Mutating API actions also require `"confirm": true` in the JSON body.

Example:

```bash
curl -H "Authorization: Bearer $SWITCHBOARD_DASHBOARD_TOKEN" http://127.0.0.1:8765/api/agents
curl -X POST -H "Authorization: Bearer $SWITCHBOARD_DASHBOARD_TOKEN" -H "Content-Type: application/json" \
  -d '{"agent":"backend","prompt":"Run tests","confirm":true}' \
  http://127.0.0.1:8765/api/send
```

Security notes: [`docs/SECURITY.md`](docs/SECURITY.md).

## Data

Default DB:

```txt
~/.switchboard/switchboard.db
```

Override for testing:

```bash
SWITCHBOARD_HOME=/tmp/switchboard-test uv run --with-editable . switchboard init
```

## Public launch checklist

Before making the repo public, run the checklist in [`docs/PUBLIC_LAUNCH_CHECKLIST.md`](docs/PUBLIC_LAUNCH_CHECKLIST.md).

## Roadmap

- 30-60s walkthrough GIF/video for the README hero
- richer dashboard editing for agents/tasks (currently CLI-driven)
- structured task artifacts (capture diffs from worktrees, not just comment text)
- agent run history with cost/latency tracking
- richer collaboration analytics

Shipped recently: per-agent git worktrees, pluggable agent kinds with TOML and entry-point loading, `switchboard run` non-interactive task dispatch, systemd installer, opt-in live mode dashboard, multi-page dashboard with active-state navigation.
