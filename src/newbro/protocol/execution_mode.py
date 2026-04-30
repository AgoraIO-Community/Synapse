from __future__ import annotations

from pydantic import BaseModel

from .enums import ExecutionMode


class TaskExecutionMode(BaseModel):
    task_id: str
    mode: ExecutionMode = ExecutionMode.UNDECIDED
    decided_from_run_id: str | None = None
    elapsed_seconds: float = 0.0
