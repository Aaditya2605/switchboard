import sqlite3

from switchboard.db import AgentRepository, init_db


def test_init_db_migrates_legacy_workflows_without_dropping_duplicate_names(tmp_path):
    db_path = tmp_path / "switchboard.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                schedule TEXT NOT NULL,
                prompt TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO workflows(name, schedule, prompt, target_agent, enabled)
            VALUES
                ('daily-check', '0 9 * * *', 'Review tasks', 'backend', 1),
                ('daily-check', '0 10 * * *', 'Review PRs', 'reviewer', 0);
            """
        )

    init_db(db_path)

    workflows = AgentRepository(db_path).list_workflows()
    assert len(workflows) == 2
    assert {workflow.prompt for workflow in workflows} == {"Review tasks", "Review PRs"}
    assert len({workflow.name for workflow in workflows}) == 2
    assert any(workflow.name == "daily-check" for workflow in workflows)
    assert any(workflow.name.startswith("daily-check-") for workflow in workflows)


def test_init_db_adds_missing_workflow_columns_idempotently(tmp_path):
    db_path = tmp_path / "switchboard.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                agent_name TEXT NOT NULL,
                prompt TEXT NOT NULL,
                cron TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO workflows(name, agent_name, prompt, cron, enabled)
            VALUES ('daily-check', 'backend', 'Review tasks', '0 9 * * *', 1);
            """
        )

    init_db(db_path)
    init_db(db_path)

    workflow = AgentRepository(db_path).get_workflow("daily-check")
    assert workflow is not None
    assert workflow.last_run_at is None
