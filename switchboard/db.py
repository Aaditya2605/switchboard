from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_TABLES = ("agents", "messages", "tasks", "runs", "workflows")


@dataclass(frozen=True)
class AgentRecord:
    name: str
    kind: str
    workdir: str
    tmux_session: str
    status: str = "running"


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
                agent_name TEXT NOT NULL,
                body TEXT NOT NULL,
                direction TEXT NOT NULL,
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
        return [self._from_row(row) for row in rows]

    def get(self, name: str) -> AgentRecord | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
        return self._from_row(row) if row else None

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
                "INSERT INTO messages(agent_name, body, direction) VALUES (?, ?, ?)",
                (agent_name, body, direction),
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> AgentRecord:
        return AgentRecord(
            name=row["name"],
            kind=row["kind"],
            workdir=row["workdir"],
            tmux_session=row["tmux_session"],
            status=row["status"],
        )
