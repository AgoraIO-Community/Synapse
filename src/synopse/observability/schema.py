from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


DiagnosticLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

LEVEL_PRIORITY: dict[DiagnosticLevel, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class DiagnosticEvent(BaseModel):
    sequence: int = 0
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    level: DiagnosticLevel
    event_name: str
    service: str = "synopse"
    component: str

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

    outcome: str | None = None
    reason_code: str | None = None
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)

    app_version: str | None = None
    git_sha: str | None = None
    model_name: str | None = None
    settings_fingerprint: str | None = None

    @model_validator(mode="after")
    def validate_reason_code(self) -> "DiagnosticEvent":
        if self.level in {"WARNING", "ERROR", "CRITICAL"} and not self.reason_code:
            raise ValueError("warning/error/critical events must include reason_code")
        return self


def level_allows(candidate: DiagnosticLevel, minimum: DiagnosticLevel) -> bool:
    return LEVEL_PRIORITY[candidate] >= LEVEL_PRIORITY[minimum]
