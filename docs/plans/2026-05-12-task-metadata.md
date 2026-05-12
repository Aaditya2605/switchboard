# Task Metadata

## Goal

Make Switchboard tasks useful as lightweight work items, not just Kanban cards.

Add metadata fields:

- `priority`: `low`, `normal`, `high`, `urgent`
- `repo`: optional repository/path/context string
- `due_date`: optional ISO `YYYY-MM-DD`
- comments: append-only notes on a task

## Scope

- SQLite schema migration for existing task tables.
- Repository/service methods for metadata and comments.
- CLI support:
  - `task add ... --priority --repo --due`
  - `task update TASK_ID [--priority] [--repo] [--due]`
  - `task comment TASK_ID BODY`
  - `task comments TASK_ID`
- Task list output should show metadata compactly.
- Telegram bridge should surface metadata in `/tasks` output.

## Out of scope

- Full dependency graph / parent-child tasks.
- Rich comment editing/deleting.
- Natural-language due date parsing.

## Verification

- Targeted tests for DB/service/CLI/Telegram behavior.
- Full pytest suite.
- CLI help smoke tests.
