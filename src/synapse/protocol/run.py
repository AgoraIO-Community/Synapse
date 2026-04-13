from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import RunStatus


class ExecutionRun(BaseModel):
    run_id: str
    task_id: str
    execution_session_id: str
    executor_type: str
    status: RunStatus = RunStatus.CREATED
    claimed_by: str | None = None
    run_revision: int = 0
    latest_progress_message: str | None = None
    output_summary: str | None = None
    block_reason: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
