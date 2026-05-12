# Switchboard Lite Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a local CLI MVP for Switchboard: persistent Claude Code/Codex agent registry, tmux-backed spawn/send/log/stop commands, and SQLite state.

**Architecture:** Python package with a Typer CLI, SQLite repository layer, and a tmux adapter. Keep tmux behind an injectable interface so tests can use a fake runner without launching real agents.

**Tech Stack:** Python 3.11+, Typer, pytest, SQLite stdlib, subprocess stdlib.

---

### Task 1: Project skeleton and DB schema

**Objective:** Create package layout and initialize SQLite tables for agents/messages/tasks/runs/workflows.

**Files:**
- Create: `pyproject.toml`
- Create: `switchboard/__init__.py`
- Create: `switchboard/db.py`
- Test: `tests/test_db.py`

**TDD:**
1. Write failing tests asserting `init_db()` creates required tables and `default_db_path()` uses `~/.switchboard/switchboard.db` unless overridden.
2. Run `pytest tests/test_db.py -v` and verify failure.
3. Implement minimal DB code.
4. Run tests and verify pass.

### Task 2: Agent repository

**Objective:** Add CRUD helpers for agent registry.

**Files:**
- Modify: `switchboard/db.py`
- Test: `tests/test_agents.py`

**TDD:**
1. Test registering/listing/getting/updating agents.
2. Verify failure.
3. Implement minimal repository functions.
4. Verify pass.

### Task 3: tmux adapter and service layer

**Objective:** Add spawn/send/log/stop behavior through an injectable command runner.

**Files:**
- Create: `switchboard/tmux.py`
- Create: `switchboard/service.py`
- Test: `tests/test_service.py`

**TDD:**
1. Test spawn builds correct tmux command for Claude and Codex.
2. Test send records message and calls `tmux send-keys`.
3. Test logs calls `tmux capture-pane`.
4. Test stop marks agent stopped and calls `tmux kill-session`.
5. Verify failures, implement, verify pass.

### Task 4: CLI

**Objective:** Expose init/agents/spawn/send/logs/stop commands.

**Files:**
- Create: `switchboard/cli.py`
- Test: `tests/test_cli.py`

**TDD:**
1. Use Typer CliRunner with temp DB.
2. Test command output and validation.
3. Verify failure, implement, verify pass.

### Task 5: README and verification

**Objective:** Document install and first commands.

**Files:**
- Create: `README.md`

**Verification:**
- Run `pytest -q`.
- Run `python -m switchboard.cli --help`.
