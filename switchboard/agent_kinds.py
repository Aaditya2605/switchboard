"""Pluggable agent-kind registry.

Switchboard supports any CLI that runs in tmux. Built-in kinds cover the
common ones (Claude Code, Codex, Aider, bash). Users add more via either:

* ``~/.switchboard/agent_kinds.toml`` (preferred for one-off local kinds)::

      [plandex]
      command = "plandex"
      description = "Plandex AI engineer"

* a Python package that registers an entry point under
  ``switchboard.agent_kinds`` (preferred for shareable plugins).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Iterable

try:  # Python 3.11+
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised only on 3.10
    tomllib = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentKind:
    """Metadata describing how to launch a single agent.

    ``command`` is the interactive form that ``switchboard spawn`` boots inside
    tmux. ``one_shot`` is an optional argv prefix for non-interactive runs
    (``switchboard run``); the task prompt is appended as the final argument.
    """

    name: str
    command: str
    description: str = ""
    one_shot: tuple[str, ...] | None = None


BUILTIN_KINDS: tuple[AgentKind, ...] = (
    AgentKind(
        name="claude",
        command="claude",
        description="Claude Code (Anthropic)",
        one_shot=("claude", "-p"),
    ),
    AgentKind(
        name="codex",
        command="codex",
        description="Codex CLI (OpenAI)",
        one_shot=("codex", "exec"),
    ),
    AgentKind(
        name="aider",
        command="aider",
        description="aider AI pair-programmer",
    ),
    AgentKind(
        name="shell",
        command="bash -i",
        description="Interactive shell for ad-hoc work",
    ),
)


class AgentKindRegistry:
    def __init__(self, kinds: Iterable[AgentKind] | None = None) -> None:
        self._kinds: dict[str, AgentKind] = {}
        for kind in kinds if kinds is not None else BUILTIN_KINDS:
            self.register(kind)

    def register(self, kind: AgentKind) -> None:
        if not kind.name:
            raise ValueError("agent kind name cannot be empty")
        if not kind.command:
            raise ValueError(f"agent kind '{kind.name}' must define a command")
        self._kinds[kind.name] = kind

    def get(self, name: str) -> AgentKind | None:
        return self._kinds.get(name)

    def require(self, name: str) -> AgentKind:
        kind = self.get(name)
        if kind is None:
            raise ValueError(
                f"Unknown agent kind: {name!r}. Known kinds: {', '.join(self.names()) or '(none)'}"
            )
        return kind

    def names(self) -> list[str]:
        return sorted(self._kinds.keys())

    def all(self) -> list[AgentKind]:
        return sorted(self._kinds.values(), key=lambda k: k.name)

    def load_from_toml(self, path: Path) -> int:
        if tomllib is None or not path.exists():
            return 0
        try:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        except Exception as exc:  # pragma: no cover - operator misconfig
            log.warning("Failed to parse %s: %s", path, exc)
            return 0
        count = 0
        for name, fields in data.items():
            if not isinstance(fields, dict):
                continue
            command = fields.get("command")
            if not command:
                continue
            one_shot_raw = fields.get("one_shot")
            one_shot: tuple[str, ...] | None
            if isinstance(one_shot_raw, list) and all(isinstance(part, str) for part in one_shot_raw):
                one_shot = tuple(one_shot_raw)
            else:
                one_shot = None
            self.register(
                AgentKind(
                    name=name,
                    command=str(command),
                    description=str(fields.get("description", "")),
                    one_shot=one_shot,
                )
            )
            count += 1
        return count

    def load_from_entry_points(self, group: str = "switchboard.agent_kinds") -> int:
        count = 0
        try:
            eps = entry_points(group=group)
        except Exception:  # pragma: no cover - older Python compatibility shim
            return 0
        for ep in eps:
            try:
                obj = ep.load()
            except Exception as exc:  # pragma: no cover - third-party failure
                log.warning("Failed to load agent kind entry point %s: %s", ep.name, exc)
                continue
            if isinstance(obj, AgentKind):
                self.register(obj)
                count += 1
            elif callable(obj):
                try:
                    kind = obj()
                except Exception as exc:  # pragma: no cover - third-party failure
                    log.warning("Failed to invoke agent kind factory %s: %s", ep.name, exc)
                    continue
                if isinstance(kind, AgentKind):
                    self.register(kind)
                    count += 1
        return count


def default_registry() -> AgentKindRegistry:
    """Build the registry actually used by the CLI: builtins + user TOML + entry points."""

    registry = AgentKindRegistry()
    # Imported lazily to avoid an import cycle.
    from switchboard.db import switchboard_home

    config = switchboard_home() / "agent_kinds.toml"
    registry.load_from_toml(config)
    registry.load_from_entry_points()
    return registry
