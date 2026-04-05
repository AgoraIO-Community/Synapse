from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import TaskStatus


class Task(BaseModel):
    task_id: str
    root_task_id: str
    parent_task_id: str | None = None
    title: str
    goal: str
    status: TaskStatus = TaskStatus.CREATED
    priority: int = 5
    interruptible: bool = True
    requires_confirmation: bool = False
    preferred_executor: str | None = None
    session_affinity: str | None = None
    task_revision: int = 0
    latest_instruction: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
