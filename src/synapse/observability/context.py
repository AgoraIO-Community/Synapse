from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass
from typing import Iterator


@dataclass(slots=True)
class DiagnosticContext:
    conversation_id: str | None = None
    request_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    execution_session_id: str | None = None
    executor_session_id: str | None = None
    notification_id: str | None = None
    trace_id: str | None = None
    worker_id: str | None = None
    executor_type: str | None = None

    def merged(self, **updates: object) -> "DiagnosticContext":
        payload = asdict(self)
        for key, value in updates.items():
            if value is not None:
                payload[key] = value
        return DiagnosticContext(**payload)


_CURRENT_CONTEXT: ContextVar[DiagnosticContext] = ContextVar(
    "synapse_diagnostic_context",
    default=DiagnosticContext(),
)


def get_diagnostic_context() -> DiagnosticContext:
    return _CURRENT_CONTEXT.get()


@contextmanager
def bind_diagnostic_context(**updates: object) -> Iterator[DiagnosticContext]:
    current = get_diagnostic_context()
    token: Token[DiagnosticContext] = _CURRENT_CONTEXT.set(current.merged(**updates))
    try:
        yield _CURRENT_CONTEXT.get()
    finally:
        _CURRENT_CONTEXT.reset(token)
