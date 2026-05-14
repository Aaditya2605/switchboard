# Switchboard Quick Demo

This demo shows the core value: one local control plane coordinating Claude Code and Codex-style agents through persistent tmux sessions, a shared task board, workflow presets, and the dashboard.

## 1. Install locally

```bash
git clone https://github.com/Aaditya2605/switchboard.git
cd switchboard
uv tool install --editable .
# or, for development:
uv run --with-editable . switchboard --help
```

## 2. Create an isolated demo home

```bash
export SWITCHBOARD_HOME=/tmp/switchboard-demo
switchboard init
```

## 3. Register two demo agents without launching tmux

```bash
switchboard spawn claude builder ~/projects/example-app --dry-run
switchboard spawn codex reviewer ~/projects/example-app --dry-run
switchboard agents
```

Remove `--dry-run` when you want real persistent tmux-backed sessions.

## 4. Add real work to the shared task board

```bash
switchboard task add "Ship auth bugfix" \
  --description "Write a regression test, fix the bug, and ask reviewer for a second pass" \
  --agent builder \
  --priority high \
  --repo ~/projects/example-app

switchboard task list
```

## 5. Install useful workflow presets

```bash
switchboard workflow install-presets --agent builder --profile launch
switchboard workflow list
```

This installs reusable workflows for code review, bugfix loops, feature building, launch audits, and daily triage.

## 6. Run the dashboard

```bash
switchboard dashboard --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

Dashboard controls include:

- send a confirmed prompt to an agent
- move tasks through the board
- create and run workflows
- load recent agent logs
- search/filter rows
- refresh summary metrics

## 7. Safer dashboard mode

If you expose the dashboard beyond localhost, require a bearer token:

```bash
export SWITCHBOARD_DASHBOARD_TOKEN=replace-with-local-token
switchboard dashboard --require-token
```

API requests then need:

```http
Authorization: Bearer [REDACTED]
```

Mutating API calls also require `"confirm": true`.
