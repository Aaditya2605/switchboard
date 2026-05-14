from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowPreset:
    name: str
    prompt: str
    cron: str
    profiles: tuple[str, ...]


PRESET_WORKFLOWS: tuple[WorkflowPreset, ...] = (
    WorkflowPreset(
        name="daily-triage",
        cron="0 9 * * *",
        profiles=("daily", "launch"),
        prompt=(
            "Review all open Switchboard tasks, agent statuses, recent inbox items, and workflow history. "
            "Return the top 3 next actions, blockers, and which agent should handle each item."
        ),
    ),
    WorkflowPreset(
        name="code-review",
        cron="0 11 * * 1-5",
        profiles=("daily", "launch"),
        prompt=(
            "Act as an independent code reviewer. Inspect the current repo diff, run the relevant tests, "
            "look for security issues, logic bugs, missing tests, and public-launch polish gaps. "
            "Return a concise pass/fail verdict with required fixes."
        ),
    ),
    WorkflowPreset(
        name="bugfix-loop",
        cron="0 13 * * 1-5",
        profiles=("daily", "launch"),
        prompt=(
            "Find the highest-impact failing test, bug report, or rough edge. Reproduce it, write or update "
            "a regression test, implement the smallest fix, run the targeted tests, and summarize the commit-ready diff."
        ),
    ),
    WorkflowPreset(
        name="feature-build",
        cron="0 15 * * 1-5",
        profiles=("launch",),
        prompt=(
            "Pick one well-scoped feature from the task board. Write the failing test first, implement the feature, "
            "update docs, run the full suite, and leave handoff notes with exact commands and changed files."
        ),
    ),
    WorkflowPreset(
        name="launch-audit",
        cron="0 17 * * 1-5",
        profiles=("launch",),
        prompt=(
            "Audit this repo as if it were going public today. Check README clarity, install path, demo flow, CI, "
            "security/secrets, screenshots, licensing, and first-user value. Return blockers and a launch checklist."
        ),
    ),
)


def workflows_for_profile(profile: str) -> tuple[WorkflowPreset, ...]:
    normalized = profile.lower().strip()
    return tuple(workflow for workflow in PRESET_WORKFLOWS if normalized in workflow.profiles)
