from __future__ import annotations

from collections import deque
from typing import Iterable

from .schema import DiagnosticEvent, DiagnosticLevel, level_allows


class InMemoryDiagnosticStore:
    def __init__(self, *, max_events: int = 500) -> None:
        self._events: deque[DiagnosticEvent] = deque(maxlen=max_events)
        self._next_sequence: int = 1

    def append(self, event: DiagnosticEvent) -> DiagnosticEvent:
        assigned = event.model_copy(update={"sequence": self._next_sequence})
        self._next_sequence += 1
        self._events.append(assigned)
        return assigned

    def query(
        self,
        *,
        after_sequence: int | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        execution_session_id: str | None = None,
        notification_id: str | None = None,
        request_id: str | None = None,
        event_prefix: str | None = None,
        min_level: DiagnosticLevel | None = None,
        limit: int = 200,
    ) -> list[DiagnosticEvent]:
        events = list(self._events)
        filtered = [
            event
            for event in events
            if _matches(
                event,
                after_sequence=after_sequence,
                task_id=task_id,
                run_id=run_id,
                execution_session_id=execution_session_id,
                notification_id=notification_id,
                request_id=request_id,
                event_prefix=event_prefix,
                min_level=min_level,
            )
        ]
        if limit <= 0:
            return []
        return filtered[-limit:]

    def all(self) -> Iterable[DiagnosticEvent]:
        return tuple(self._events)


def _matches(
    event: DiagnosticEvent,
    *,
    after_sequence: int | None,
    task_id: str | None,
    run_id: str | None,
    execution_session_id: str | None,
    notification_id: str | None,
    request_id: str | None,
    event_prefix: str | None,
    min_level: DiagnosticLevel | None,
) -> bool:
    if after_sequence is not None and event.sequence <= after_sequence:
        return False
    if task_id and event.task_id != task_id:
        return False
    if run_id and event.run_id != run_id:
        return False
    if execution_session_id and event.execution_session_id != execution_session_id:
        return False
    if notification_id and event.notification_id != notification_id:
        return False
    if request_id and event.request_id != request_id:
        return False
    if event_prefix and not event.event_name.startswith(event_prefix):
        return False
    if min_level and not level_allows(event.level, min_level):
        return False
    return True
