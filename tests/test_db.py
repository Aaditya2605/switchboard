from pathlib import Path

from switchboard.db import default_db_path, init_db, list_tables


def test_default_db_path_uses_switchboard_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SWITCHBOARD_HOME", str(tmp_path))

    assert default_db_path() == tmp_path / "switchboard.db"


def test_init_db_creates_required_tables(tmp_path):
    db_path = tmp_path / "switchboard.db"

    init_db(db_path)

    assert set(list_tables(db_path)) >= {
        "agents",
        "messages",
        "tasks",
        "runs",
        "workflows",
    }
