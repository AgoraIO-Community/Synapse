from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from runtime.infrastructure.time import utc_now
from runtime.protocols.tasks import Artifact, Task, TaskStatus


class ExecutionRequestType(StrEnum):
    START = "start"
    UPDATE = "update"
    CONTROL = "control"


class ExecutionEventType(StrEnum):
    ACCEPTED = "accepted"
    STARTED = "started"
    PROGRESS = "progress"
    BLOCKED = "blocked"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ExecutorCapability(BaseModel):
    executor_id: str
    label: str
    capability_tags: list[str] = Field(default_factory=list)
    supports_cancel: bool = True
    supports_pause: bool = True
    supports_streaming: bool = True


class ExecutionRequest(BaseModel):
    request_id: str
    task_id: str
    executor_id: str
    request_type: ExecutionRequestType
    task_snapshot: Task
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: Any = Field(default_factory=utc_now)


class ExecutionEvent(BaseModel):
    event_id: str
    task_id: str
    executor_id: str
    event_type: ExecutionEventType
    status: TaskStatus
    progress_message: str | None = None
    progress_percent: float | None = None
    source: str = "executor"
    artifacts_delta: list[Artifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: Any = Field(default_factory=utc_now)


class ExecutionResult(BaseModel):
    result_id: str
    task_id: str
    executor_id: str
    final_status: TaskStatus
    summary: str | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: Any = Field(default_factory=utc_now)
