from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import MutationType


class TaskMutation(BaseModel):
    mutation_id: str
    task_id: str | None = None
    mutation_type: MutationType
    patch: dict[str, object] = Field(default_factory=dict)
    created_by: str
    urgency: str = "normal"
    effective_scope: str = "task"
    requires_replan: bool = False
