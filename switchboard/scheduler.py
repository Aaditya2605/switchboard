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
    return all(
        [
            _field_matches(minute, now.minute),
            _field_matches(hour, now.hour),
            _field_matches(day, now.day),
            _field_matches(month, now.month),
            _field_matches(weekday, now.weekday()),
        ]
    )


def _field_matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    if not field.isdigit():
        raise ValueError(f"Unsupported cron field: {field}")
    return int(field) == value


def _already_ran_this_minute(workflow: WorkflowRecord, now: datetime) -> bool:
    if workflow.last_run_at is None:
        return False
    try:
        last_run = datetime.fromisoformat(workflow.last_run_at)
    except ValueError:
        last_run = datetime.strptime(workflow.last_run_at, "%Y-%m-%d %H:%M:%S")
    return last_run.replace(second=0, microsecond=0) == now.replace(second=0, microsecond=0)
