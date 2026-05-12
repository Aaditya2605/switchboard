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
                name TEXT NOT NULL,
                schedule TEXT NOT NULL,
                prompt TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    return path


def list_tables(db_path: Path | None = None) -> list[str]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [row["name"] for row in rows]


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
