from __future__ import annotations

from pydantic import BaseModel


class TaskSummary(BaseModel):
    task_id: str
    operational_summary: str | None = None
    conversational_summary: str | None = None
    latest_user_visible_status: str | None = None
    needs_user_input: bool = False
