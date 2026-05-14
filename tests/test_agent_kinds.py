from __future__ import annotations

import pytest

from switchboard.agent_kinds import (
    BUILTIN_KINDS,
    AgentKind,
    AgentKindRegistry,
    default_registry,
)


def test_builtin_registry_has_claude_codex_aider_and_shell():
    registry = AgentKindRegistry()
    assert {k.name for k in registry.all()} >= {"claude", "codex", "aider", "shell"}


def test_builtin_kinds_commands_match_names_or_documented_override():
    by_name = {kind.name: kind for kind in BUILTIN_KINDS}
    assert by_name["claude"].command == "claude"
    assert by_name["codex"].command == "codex"
    assert by_name["aider"].command == "aider"
    assert by_name["shell"].command.startswith("bash")


def test_register_then_require_round_trips_a_custom_kind():
    registry = AgentKindRegistry()
    registry.register(AgentKind(name="plandex", command="plandex", description="Plandex"))
    assert registry.require("plandex").command == "plandex"
    assert "plandex" in registry.names()


def test_require_raises_for_unknown_kind():
    registry = AgentKindRegistry()
    with pytest.raises(ValueError) as exc:
        registry.require("not-a-kind")
    assert "not-a-kind" in str(exc.value)
    assert "claude" in str(exc.value)  # mentions known kinds


def test_register_validates_name_and_command():
    registry = AgentKindRegistry(kinds=[])
    with pytest.raises(ValueError):
        registry.register(AgentKind(name="", command="x"))
    with pytest.raises(ValueError):
        registry.register(AgentKind(name="x", command=""))


def test_load_from_toml_adds_user_kinds(tmp_path):
    config = tmp_path / "agent_kinds.toml"
    config.write_text(
        """
[plandex]
command = "plandex"
description = "Plandex"

[my-claude]
command = "claude --resume"
"""
    )
    registry = AgentKindRegistry()
    loaded = registry.load_from_toml(config)
    assert loaded == 2
    assert registry.require("plandex").command == "plandex"
    assert registry.require("my-claude").command == "claude --resume"


def test_load_from_toml_silently_ignores_missing_file(tmp_path):
    registry = AgentKindRegistry()
    assert registry.load_from_toml(tmp_path / "nope.toml") == 0


def test_default_registry_loads_user_config_when_present(tmp_path, monkeypatch):
    home = tmp_path / "switchboard-home"
    home.mkdir()
    (home / "agent_kinds.toml").write_text("[custom]\ncommand = \"custom-cli\"\n")
    monkeypatch.setenv("SWITCHBOARD_HOME", str(home))
    registry = default_registry()
    assert registry.require("custom").command == "custom-cli"
    # Builtins still present.
    assert "claude" in registry.names()
