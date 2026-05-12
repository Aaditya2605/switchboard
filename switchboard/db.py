from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


REQUIRED_TABLES = ("agents", "messages", "tasks", "runs", "workflows")
VALID_TASK_STATUSES = {"assigned", "in_progress", "blocked", "completed"}


@dataclass(frozen=True)
class AgentRecord:
    name: str
    kind: str
    workdir: str
    tmux_session: str
    status: str = "running"


@dataclass(frozen=True)
class MessageRecord:
    id: int
    from_agent: str
    to_agent: str
    body: str
    delivered_at: str | None = None


@dataclass(frozen=True)
class TaskRecord:
    id: int
    title: str
    description: str = ""
    status: str = "assigned"
    assigned_agent: str | None = None


@dataclass(frozen=True)
class WorkflowRecord:
    id: int
    name: str
    agent_name: str
    prompt: str
    cron: str
    enabled: bool = True
    last_run_at: str | None = None


def switchboard_home() -> Path:
    return Path(os.environ.get("SWITCHBOARD_HOME", "~/.switchboard")).expanduser()


def default_db_path() -> Path:
    return switchboard_home() / "switchboard.db"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or default_db_path()
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                name TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                workdir TEXT NOT NULL,
                tmux_session TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                from_agent TEXT,
                to_agent TEXT,
                body TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'agent_to_agent',
                delivered_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'assigned',
                assigned_agent TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                command TEXT NOT NULL,
                output TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                agent_name TEXT NOT NULL,
                prompt TEXT NOT NULL,
                cron TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        _migrate_workflows(conn)
    return path


def list_tables(db_path: Path | None = None) -> list[str]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [row["name"] for row in rows]


def _workflow_columns(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(workflows)").fetchall()}


def _create_workflows_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            agent_name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            cron TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_run_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _migrate_workflows(conn: sqlite3.Connection) -> None:
    columns = _workflow_columns(conn)
    if {"agent_name", "cron", "last_run_at", "updated_at"}.issubset(columns):
        return

    if {"agent_name", "cron"}.issubset(columns):
        if "last_run_at" not in columns:
            conn.execute("ALTER TABLE workflows ADD COLUMN last_run_at TEXT")
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE workflows ADD COLUMN updated_at TEXT")
        return

    if {"target_agent", "schedule"}.issubset(columns):
        rows = conn.execute(
            "SELECT id, name, target_agent, prompt, schedule, enabled, created_at FROM workflows ORDER BY id"
        ).fetchall()
        conn.execute("ALTER TABLE workflows RENAME TO workflows_legacy")
        _create_workflows_table(conn)
        used_names: set[str] = set()
        for row in rows:
            name = row["name"]
            if name in used_names:
                name = f"{name}-{row['id']}"
            used_names.add(name)
            conn.execute(
                """
                INSERT INTO workflows(id, name, agent_name, prompt, cron, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row["id"], name, row["target_agent"], row["prompt"], row["schedule"], row["enabled"], row["created_at"]),
            )
        conn.execute("DROP TABLE workflows_legacy")
        return

    raise RuntimeError(f"Unsupported workflows schema columns: {sorted(columns)}")


class AgentRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or default_db_path()

    def register(self, name: str, kind: str, workdir: str, tmux_session: str) -> AgentRecord:
        record = AgentRecord(name=name, kind=kind, workdir=workdir, tmux_session=tmux_session)
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO agents(name, kind, workdir, tmux_session, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    kind=excluded.kind,
                    workdir=excluded.workdir,
                    tmux_session=excluded.tmux_session,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (record.name, record.kind, record.workdir, record.tmux_session, record.status),
            )
        return record

    def list(self) -> list[AgentRecord]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM agents ORDER BY name").fetchall()
        return [self._agent_from_row(row) for row in rows]

    def get(self, name: str) -> AgentRecord | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
        return self._agent_from_row(row) if row else None

    def update_status(self, name: str, status: str) -> AgentRecord:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE agents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                (status, name),
            )
        agent = self.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name}")
        return agent

    def record_message(self, agent_name: str, body: str, direction: str = "outbound") -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages(agent_name, to_agent, body, direction) VALUES (?, ?, ?, ?)",
                (agent_name, agent_name, body, direction),
            )

    def create_message(self, from_agent: str, to_agent: str, body: str) -> MessageRecord:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(from_agent, to_agent, body, direction)
                VALUES (?, ?, ?, 'agent_to_agent')
                """,
                (from_agent, to_agent, body),
            )
            msg_id = cur.lastrowid
        message = self.get_message(msg_id)
        assert message is not None
        return message

    def get_message(self, message_id: int) -> MessageRecord | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return self._message_from_row(row) if row else None

    def inbox(self, to_agent: str) -> list[MessageRecord]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE to_agent = ? AND direction = 'agent_to_agent' AND delivered_at IS NULL
                ORDER BY id
                """,
                (to_agent,),
            ).fetchall()
        return [self._message_from_row(row) for row in rows]

    def mark_delivered(self, message_id: int) -> MessageRecord:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE messages SET delivered_at = CURRENT_TIMESTAMP WHERE id = ?",
                (message_id,),
            )
        message = self.get_message(message_id)
        if message is None:
            raise KeyError(f"Unknown message: {message_id}")
        return message

    def create_task(self, title: str, description: str = "", assigned_agent: str | None = None) -> TaskRecord:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO tasks(title, description, assigned_agent) VALUES (?, ?, ?)",
                (title, description, assigned_agent),
            )
            task_id = cur.lastrowid
        task = self.get_task(task_id)
        assert task is not None
        return task

    def list_tasks(self, status: str | None = None) -> list[TaskRecord]:
        with connect(self.db_path) as conn:
            if status:
                rows = conn.execute("SELECT * FROM tasks WHERE status = ? ORDER BY id", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
        return [self._task_from_row(row) for row in rows]

    def get_task(self, task_id: int) -> TaskRecord | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._task_from_row(row) if row else None

    def assign_task(self, task_id: int, agent_name: str) -> TaskRecord:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE tasks SET assigned_agent = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (agent_name, task_id),
            )
        return self._require_task(task_id)

    def move_task(self, task_id: int, status: str) -> TaskRecord:
        if status not in VALID_TASK_STATUSES:
            raise ValueError(f"Invalid task status: {status}")
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, task_id),
            )
        return self._require_task(task_id)

    def create_workflow(self, name: str, agent_name: str, prompt: str, cron: str) -> WorkflowRecord:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO workflows(name, agent_name, prompt, cron)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    agent_name=excluded.agent_name,
                    prompt=excluded.prompt,
                    cron=excluded.cron,
                    enabled=1,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (name, agent_name, prompt, cron),
            )
        workflow = self.get_workflow(name)
        assert workflow is not None
        return workflow

    def list_workflows(self) -> list[WorkflowRecord]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM workflows ORDER BY name").fetchall()
        return [self._workflow_from_row(row) for row in rows]

    def get_workflow(self, name: str) -> WorkflowRecord | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM workflows WHERE name = ?", (name,)).fetchone()
        return self._workflow_from_row(row) if row else None

    def get_workflow_by_id(self, workflow_id: int) -> WorkflowRecord | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        return self._workflow_from_row(row) if row else None

    def set_workflow_enabled(self, name: str, enabled: bool) -> WorkflowRecord:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE workflows SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                (1 if enabled else 0, name),
            )
        return self._require_workflow(name)

    def mark_workflow_run(self, name: str) -> WorkflowRecord:
        with connect(self.db_path) as conn:
            conn.execute(
                "UPDATE workflows SET last_run_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                (name,),
            )
        return self._require_workflow(name)

    def _require_workflow(self, name: str) -> WorkflowRecord:
        workflow = self.get_workflow(name)
        if workflow is None:
            raise KeyError(f"Unknown workflow: {name}")
        return workflow

    def _require_task(self, task_id: int) -> TaskRecord:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        return task

    @staticmethod
    def _agent_from_row(row: sqlite3.Row) -> AgentRecord:
        return AgentRecord(
            name=row["name"],
            kind=row["kind"],
            workdir=row["workdir"],
            tmux_session=row["tmux_session"],
            status=row["status"],
        )

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> MessageRecord:
        return MessageRecord(
            id=row["id"],
            from_agent=row["from_agent"] or row["agent_name"] or "user",
            to_agent=row["to_agent"] or row["agent_name"] or "unknown",
            body=row["body"],
            delivered_at=row["delivered_at"],
        )

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            assigned_agent=row["assigned_agent"],
        )

    @staticmethod
    def _workflow_from_row(row: sqlite3.Row) -> WorkflowRecord:
        return WorkflowRecord(
            id=row["id"],
            name=row["name"],
            agent_name=row["agent_name"],
            prompt=row["prompt"],
            cron=row["cron"],
            enabled=bool(row["enabled"]),
            last_run_at=row["last_run_at"],
        )
