from __future__ import annotations

from dataclasses import dataclass

from synapse.blackboard import BlackboardWriteEvent, BlackboardWriteKind

from ..logger import DiagnosticLogger


@dataclass(slots=True)
class BlackboardDiagnosticEmitter:
    logger: DiagnosticLogger

    def record_write(
        self,
        *,
        event: BlackboardWriteEvent,
        created: bool,
    ) -> None:
        event_name = _event_name(event.kind, created=created)
        if event_name is None:
            return
        self.logger.emit_event(
            level="INFO",
            event_name=event_name,
            component="blackboard.store",
            summary="Blackboard projection updated",
            request_id=event.request_id,
            task_id=event.task_id,
            run_id=event.entity_id if event.kind == BlackboardWriteKind.RUN else None,
            execution_session_id=(
                event.entity_id if event.kind == BlackboardWriteKind.SESSION else None
            ),
            notification_id=(
                event.entity_id if event.kind == BlackboardWriteKind.NOTIFICATION else None
            ),
            details=event.payload,
        )


def _event_name(kind: BlackboardWriteKind, *, created: bool) -> str | None:
    if kind == BlackboardWriteKind.TASK:
        return "bb.task.created" if created else "bb.task.updated"
    if kind == BlackboardWriteKind.MUTATION:
        return "bb.mutation.appended"
    if kind == BlackboardWriteKind.COMMAND:
        return "bb.command.appended"
    if kind == BlackboardWriteKind.RUN:
        return "bb.run.updated"
    if kind == BlackboardWriteKind.SESSION:
        return "bb.session.created" if created else "bb.session.updated"
    if kind == BlackboardWriteKind.BINDING:
        return "bb.binding.updated"
    if kind == BlackboardWriteKind.SUMMARY:
        return "bb.summary.updated"
    if kind == BlackboardWriteKind.EXECUTION_MODE:
        return "bb.execution_mode.updated"
    if kind == BlackboardWriteKind.NOTIFICATION:
        return "bb.notification.candidate.created" if created else "bb.notification.candidate.updated"
    return None
