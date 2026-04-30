from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import TaskCommandType


class TaskCommand(BaseModel):
    command_id: str
    task_id: str
    command_type: TaskCommandType
    payload: dict[str, object] = Field(default_factory=dict)
    created_by: str
    reason: str | None = None
