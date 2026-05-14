# Changelog

All notable changes to Switchboard follow this file. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- `switchboard spawn --worktree` puts each agent in its own `git worktree` rooted at `$SWITCHBOARD_HOME/worktrees/<name>` on a `switchboard/<name>` branch. New `switchboard worktree list` / `prune --confirm` commands.
- Pluggable agent-kind registry. Built-in: `claude`, `codex`, `aider`, `shell`. Extend via `~/.switchboard/agent_kinds.toml` or a `switchboard.agent_kinds` entry point group. `switchboard kinds` lists them.
- `switchboard run <task-id>` dispatches a task to its assigned agent's non-interactive CLI (`claude -p`, `codex exec`, ...), captures the response as a task comment, and optionally marks the task done.
- `switchboard run-batch [ids...] [--status STATUS] [--max N]` parallel dispatch via thread pool with per-task pass/fail.
- Per-task detail page in the dashboard (`/tasks/<id>`) shows description, status moves, and the full comment thread (which is where `switchboard run` captures each agent's response).
- Linux systemd user-unit installer for the scheduler (`scheduler install-systemd`, `uninstall-systemd`, `systemd-status`).
- Opt-in dashboard live mode — toggle in the sidebar, polls `/api/summary` every 10s and reloads only on state change. State persists per-browser via localStorage.
- Multi-page dashboard: every nav item is a dedicated route (`/agents`, `/tasks`, `/workflows`, …). Sidebar highlights the active page. A new `/search` page filters across agents, tasks, and workflows server-side.
- Per-page client-side row filter inputs on the agents, tasks, and workflows pages.
- Real screenshots replace the placeholder SVG hero (`docs/assets/dashboard-preview.png` plus 8 per-page captures under `docs/assets/screenshots/`).

### Fixed

- Cron parser now supports the full common syntax — ranges (`1-5`), lists (`0,30`), steps (`*/15`), and cron weekday numbering (`0`/`7` = Sunday). Bundled presets like `code-review` previously crashed `scheduler tick` with `Unsupported cron field: 1-5`.
- Workflow create form and log viewer placeholder no longer render in the browser default monospace font; styles were scoped to `.command-card` only.

### Changed

- `AgentRecord` now carries optional `worktree_path` and `worktree_branch` fields. Migration is additive: existing databases pick up the columns on next `init`.
- `TmuxClient.start_agent` now takes the resolved shell command directly. Per-kind dispatch moved into `switchboard.agent_kinds`.
- Dashboard `agents` table grew a Worktree column.

## 0.1.0 history (pre-public)

- `feat: scaffold switchboard lite`
- `feat: add comms inbox and task board`
- `feat: add workflow prompt dispatch`
- `feat: add workflow scheduler daemon`
- `feat: add telegram command bridge`
- `feat: add agent health checks`
- `feat: add task metadata and comments`
- `feat: add launchd scheduler installer`
- `feat: add telegram bot integration`
- `feat: add fastapi dashboard`
- `feat: add dashboard auth safeguards`
- `feat: polish dashboard control plane`
- `feat: prep switchboard for public launch`
