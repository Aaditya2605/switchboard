from switchboard.db import AgentRecord, AgentRepository, init_db


def test_register_and_list_agent(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    repo = AgentRepository(db_path)

    agent = repo.register(
        name="backend",
        kind="claude",
        workdir="/tmp/project",
        tmux_session="switchboard-backend",
    )

    assert agent.name == "backend"
    assert agent.status == "running"
    assert repo.get("backend") == agent
    assert repo.list() == [agent]


def test_update_agent_status(tmp_path):
    db_path = tmp_path / "switchboard.db"
    init_db(db_path)
    repo = AgentRepository(db_path)
    repo.register("reviewer", "codex", "/tmp/project", "switchboard-reviewer")

    updated = repo.update_status("reviewer", "stopped")

    assert updated.status == "stopped"
    assert repo.get("reviewer").status == "stopped"
