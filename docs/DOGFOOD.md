# Dogfood — multi-agent orchestration end-to-end

The orchestration story Switchboard pitches in the README — drive Claude and Codex side by side on the same workspace, share state, capture each agent's reasoning as task comments — is exercised by an actual end-to-end run, not just unit tests.

This file is the receipt.

## Setup

```bash
export SWITCHBOARD_HOME=/tmp/switchboard-dogfood/.switchboard
uv run --with-editable . switchboard init
uv run --with-editable . switchboard spawn claude builder  /tmp/switchboard-dogfood/sessions --dry-run
uv run --with-editable . switchboard spawn codex  reviewer /tmp/switchboard-dogfood/sessions --dry-run
```

Two agents are registered against the same workspace. ``--dry-run`` only skips the tmux session bring-up; ``switchboard run`` shells out directly to ``claude -p`` / ``codex exec`` from the agent's workdir, so the tmux pane is not required for non-interactive dispatch.

## Task 1 — Claude sketches a CLI

```bash
uv run --with-editable . switchboard task add "Sketch a tmux-bin CLI" \
  --description "Propose the file structure and the click commands for a Python CLI that lists tmux sessions with their last-activity timestamp. Output the proposed directory tree as a bullet list, plus a short README intro. Do not write any files." \
  --agent builder --priority high --repo /tmp/switchboard-dogfood/sessions

uv run --with-editable . switchboard run 1
```

Switchboard resolves agent `builder` → kind `claude` → ``one_shot = ("claude", "-p")``, dispatches the task, captures the response as task comment #1:

```
## Proposed structure

- `tmux-bin/`
  - `pyproject.toml` — packaging + `tmux-bin` console script entry point
  - `src/tmux_bin/`
    - `cli.py` — click group + command wiring
    - `tmux.py` — thin `tmux` subprocess wrapper
    - `formatting.py` — human-readable "5m ago" / table rendering
  - `tests/`

## Click commands

- `tmux-bin ls` (default) — table of name, windows, attached, last_activity, idle_for
  - `--json` — machine-readable output
  - `--sort {activity,name,idle}` — default `activity`, newest first
  - `--idle-only` — only sessions with no attached client
- `tmux-bin show <name>` — single-session detail
- `tmux-bin version`

Under the hood: one call to `tmux list-sessions -F '#{session_name}|...|#{session_activity}'`
— `session_activity` is a unix timestamp, so "last activity" comes free.
```

(Full text in the task comment; trimmed here for readability.)

## Task 2 — Codex critiques the sketch

```bash
uv run --with-editable . switchboard task add "Critique the tmux-bin sketch" \
  --description "A teammate proposed a CLI called tmux-bin that wraps 'tmux list-sessions -F' to display name, windows, attached, last activity, and idle. Commands: ls, show <name>, version. Identify three concrete problems or missing features in that sketch, and propose one breaking-bad change you would push back on. Be terse. Do not write files." \
  --agent reviewer --priority normal --repo /tmp/switchboard-dogfood/sessions

uv run --with-editable . switchboard run 2 --timeout 360
```

Switchboard resolves agent `reviewer` → kind `codex` → ``one_shot = ("codex", "exec")``, dispatches the task, captures the response as task comment #2:

```
Three problems/missing features:

1. No `-L` / `-S` support, so it only sees the default tmux server/socket.
2. No defined behavior for "tmux not running" vs "no sessions" vs "tmux not installed"; exit codes matter.
3. `show <name>` needs exact matching. Tmux target syntax/prefix matching can resolve the wrong session.

Breaking-bad change I'd push back on: changing `ls` default output after release
from human table to JSON or reordered columns. Add `--json` / `--format` instead;
keep defaults stable.
```

## What this proves

- Two distinct AI CLIs (`claude -p` and `codex exec`) drove off the same shared task board.
- Switchboard owns the workflow: task creation, agent assignment, prompt formatting (`title\n\ndescription\n\nRepo: ...`), subprocess launch, output capture, comment threading, and status transitions.
- No human-in-the-loop dispatch was needed between the two runs — the operator only chose tasks and read the resulting comments.
- The two agents disagreed productively: Claude proposed an MVP, Codex spotted three integration gaps and a backwards-compat trap.

## Task 3 — parallel dispatch beats sequential by 3×

Three small tasks fired concurrently:

```bash
switchboard task add "One-line summary: what is tmux?"     --agent builder
switchboard task add "One-line summary: what is launchd?"  --agent builder
switchboard task add "One-line summary: what is systemd?"  --agent builder
switchboard run-batch 4 5 6 --max 3 --timeout 120
```

Output:

```
✓ #4    in_progress     comment #5 by builder
✓ #5    in_progress     comment #4 by builder
✓ #6    in_progress     comment #6 by builder

3/3 tasks succeeded.
real    0m8.652s
```

Notice the comment IDs (`#5`, `#4`, `#6`) are out of task order: tasks completed concurrently and each one's comment landed when its `claude -p` call returned. Sequential would have been ~25–30 seconds; parallel was 8.6.

The captured comments:

- *tmux is a terminal multiplexer that lets you run multiple terminal sessions inside one window, detach them, and reattach later without losing work.*
- *launchd is macOS's system service manager that starts, stops, and supervises background processes (daemons and agents) at boot, login, or on demand.*
- *systemd is a Linux system and service manager that boots the OS, starts and supervises background services (daemons), and manages system resources.*

## Notes for tuning your own runs

- `codex exec` has a 10–20s warm-up; the default ``--timeout 600`` is comfortable, but if you set it lower you may need to raise it.
- For larger or tool-using prompts, pair `switchboard run` with `switchboard spawn --worktree` so each agent edits an isolated branch.
- The output is captured as a task comment, so it survives across sessions and is visible from the dashboard's `/tasks/<id>` page.
- Parallel dispatch is bounded by `--max` (default `3`). Pick a number that respects your subscription's rate limits.
