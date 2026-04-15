from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .context import get_diagnostic_context
from .redaction import sanitize_details
from .schema import DiagnosticEvent, DiagnosticLevel, level_allows
from .store import InMemoryDiagnosticStore
from .sinks.types import DiagnosticSink


@dataclass(slots=True)
class DiagnosticLogger:
    store: InMemoryDiagnosticStore
    sinks: list[DiagnosticSink] = field(default_factory=list)
    min_level: DiagnosticLevel = "INFO"
    debug_details: bool = False
    app_version: str | None = None
    git_sha: str | None = None
    model_name: str | None = None
    settings_fingerprint: str | None = None

    def emit_event(
        self,
        *,
        level: DiagnosticLevel,
        event_name: str,
        component: str,
        summary: str,
        outcome: str | None = None,
        reason_code: str | None = None,
        details: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        request_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        execution_session_id: str | None = None,
        executor_session_id: str | None = None,
        notification_id: str | None = None,
        trace_id: str | None = None,
        worker_id: str | None = None,
        executor_type: str | None = None,
    ) -> DiagnosticEvent | None:
        context = get_diagnostic_context()
        event = DiagnosticEvent(
            level=level,
            event_name=event_name,
            component=component,
            conversation_id=conversation_id or context.conversation_id,
            request_id=request_id or context.request_id,
            task_id=task_id or context.task_id,
            run_id=run_id or context.run_id,
            execution_session_id=execution_session_id or context.execution_session_id,
            executor_session_id=executor_session_id or context.executor_session_id,
            notification_id=notification_id or context.notification_id,
            trace_id=trace_id or context.trace_id,
            worker_id=worker_id or context.worker_id,
            executor_type=executor_type or context.executor_type,
            outcome=outcome,
            reason_code=reason_code,
            summary=summary,
            details=sanitize_details(details, debug_enabled=self.debug_details and level == "DEBUG"),
            app_version=self.app_version,
            git_sha=self.git_sha,
            model_name=self.model_name,
            settings_fingerprint=self.settings_fingerprint,
        )
        event = self.store.append(event)
        if level_allows(level, self.min_level):
            for sink in self.sinks:
                sink.emit(event)
        return event
