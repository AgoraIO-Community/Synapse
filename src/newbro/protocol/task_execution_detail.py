from __future__ import annotations

from pydantic import BaseModel, Field


class TaskExecutionDetailEntry(BaseModel):
    detail_id: str
    task_id: str
    run_id: str
    execution_session_id: str
    event_type: str
    text: str
    created_at: str
    payload: dict[str, object] = Field(default_factory=dict)
