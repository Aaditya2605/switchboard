from __future__ import annotations

from datetime import datetime

from switchboard.db import WorkflowRecord
from switchboard.service import SwitchboardService


class Scheduler:
    def __init__(self, service: SwitchboardService):
        self.service = service

    def tick(self, now: datetime | None = None) -> list[WorkflowRecord]:
        now = now or datetime.utcnow()
        ran: list[WorkflowRecord] = []
        for workflow in self.service.list_workflows():
            if not workflow.enabled:
                continue
            if not cron_matches(workflow.cron, now):
                continue
            if _already_ran_this_minute(workflow, now):
                continue
            ran.append(self.service.run_workflow(workflow.name, ran_at=now.isoformat()))
        return ran


def cron_matches(cron: str, now: datetime) -> bool:
    fields = cron.split()
    if len(fields) != 5:
        raise ValueError("cron must be a five-field expression")
    minute, hour, day, month, weekday = fields
    minutes = _expand_field(minute, 0, 59)
    hours = _expand_field(hour, 0, 23)
    days = _expand_field(day, 1, 31)
    months = _expand_field(month, 1, 12)
    weekdays = _expand_weekday(weekday)
    return (
        now.minute in minutes
        and now.hour in hours
        and now.day in days
        and now.month in months
        and now.weekday() in weekdays
    )


def _expand_field(field: str, lo: int, hi: int) -> set[int]:
    """Expand a cron field into the set of integers it matches.

    Supports ``*``, single values, ranges ``a-b``, lists ``a,b,c``, and steps
    ``*/n``/``a-b/n``. Values outside ``[lo, hi]`` are dropped.
    """

    result: set[int] = set()
    for part in field.split(","):
        if not part:
            raise ValueError(f"empty cron field segment: {field!r}")
        base, _, step_str = part.partition("/")
        try:
            step = int(step_str) if step_str else 1
        except ValueError as exc:
            raise ValueError(f"invalid step in cron field {field!r}: {step_str!r}") from exc
        if step <= 0:
            raise ValueError(f"step must be positive in cron field {field!r}")
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            start_s, _, end_s = base.partition("-")
            try:
                start, end = int(start_s), int(end_s)
            except ValueError as exc:
                raise ValueError(f"invalid range in cron field {field!r}") from exc
        else:
            try:
                start = end = int(base)
            except ValueError as exc:
                raise ValueError(f"unsupported cron field segment: {part!r}") from exc
        if start > end:
            raise ValueError(f"reversed range in cron field {field!r}")
        for value in range(start, end + 1, step):
            if lo <= value <= hi:
                result.add(value)
    if not result:
        raise ValueError(f"cron field {field!r} matches nothing in range {lo}-{hi}")
    return result


def _expand_weekday(field: str) -> set[int]:
    """Cron weekday (0 or 7 = Sun, 1-6 = Mon-Sat) → Python weekday (0 = Mon)."""

    cron_values = _expand_field(field, 0, 7)
    return {(value - 1) % 7 for value in cron_values}


def _already_ran_this_minute(workflow: WorkflowRecord, now: datetime) -> bool:
    if workflow.last_run_at is None:
        return False
    try:
        last_run = datetime.fromisoformat(workflow.last_run_at)
    except ValueError:
        last_run = datetime.strptime(workflow.last_run_at, "%Y-%m-%d %H:%M:%S")
    return last_run.replace(second=0, microsecond=0) == now.replace(second=0, microsecond=0)
