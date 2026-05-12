# Switchboard Comms + Tasks Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add agent-to-agent message inbox and shared Kanban-style task board to Switchboard Lite.

**Architecture:** Extend SQLite repository layer with MessageRecord and TaskRecord dataclasses. Add service methods and CLI command groups for messages and tasks. Keep commands simple and testable.

**Tech Stack:** Python 3.11+, Typer, pytest, SQLite stdlib.

---

### Task 1: Message repository and service

**Objective:** Store agent-to-agent messages and expose list/relay behavior.

**Files:**
- Modify: `switchboard/db.py`
- Modify: `switchboard/service.py`
- Test: `tests/test_messages.py`

**TDD:**
1. Test `send_agent_message(from_agent, to_agent, body)` stores a message.
2. Test inbox returns undelivered messages for target agent.
3. Test relay injects a formatted message into the recipient agent via tmux send.
4. Verify failure, implement, verify pass.

### Task 2: Task repository and service

**Objective:** Add task creation/listing/assignment/status transitions.

**Files:**
- Modify: `switchboard/db.py`
- Modify: `switchboard/service.py`
- Test: `tests/test_tasks.py`

**TDD:**
1. Test create/list tasks.
2. Test assign task to agent.
3. Test moving task through assigned/in_progress/blocked/completed.
4. Verify failure, implement, verify pass.

### Task 3: CLI commands

**Objective:** Expose comms and task board via Typer commands.

**Files:**
- Modify: `switchboard/cli.py`
- Test: `tests/test_cli_comms_tasks.py`

**Commands:**
- `switchboard msg FROM TO BODY [--deliver]`
- `switchboard inbox AGENT`
- `switchboard task add TITLE --description TEXT --agent AGENT`
- `switchboard task list [--status STATUS]`
- `switchboard task assign TASK_ID AGENT`
- `switchboard task move TASK_ID STATUS`

### Task 4: Docs and verification

**Objective:** Update README and run tests.

**Verification:**
- `uv run --with-editable . --with pytest pytest -q`
- `uv run --with-editable . switchboard --help`
