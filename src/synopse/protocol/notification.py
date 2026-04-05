from __future__ import annotations

from pydantic import BaseModel

from .enums import NotificationPriority


class NotificationCandidate(BaseModel):
    candidate_id: str
    task_id: str
    priority: NotificationPriority
    summary_short: str
    requires_immediate_delivery: bool = False
