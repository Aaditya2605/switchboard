# Switchboard Workflow/Cron Prompts

## Goal
Add workflow prompt storage and manual dispatch so Switchboard can save reusable/scheduled prompts and inject them into Claude/Codex agents.

## Scope
- SQLite workflow records with name, agent, prompt, cron expression, enabled flag, and timestamps.
- Service methods to add/list/enable/disable/run workflows.
- CLI commands under `workflow`:
  - `workflow add NAME --agent AGENT --prompt PROMPT --cron CRON`
  - `workflow list`
  - `workflow run NAME`
  - `workflow disable NAME`
  - `workflow enable NAME`
- `workflow run` sends a formatted prompt into the target agent tmux session.

## Non-goals for this increment
- A long-running scheduler daemon.
- Real cron parsing/execution loop.
- Telegram controls.

## Tests first
- DB repository tests for create/list/get/toggle.
- Service tests for validation and dispatch through fake tmux runner.
- CLI tests for add/list/run/toggle.

## Verification
- Targeted workflow tests pass.
- Full test suite passes.
- CLI help exposes `workflow` commands.
- Commit changes.
