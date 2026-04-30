from __future__ import annotations

from pydantic import BaseModel

from .enums import (
    NotificationCandidateType,
    NotificationDeliveryStatus,
    NotificationPriority,
)


class NotificationCandidate(BaseModel):
    candidate_id: str
    task_id: str
    candidate_type: NotificationCandidateType
    priority: NotificationPriority
    summary_short: str
    source_run_id: str | None = None
    created_at: str
    delivery_status: NotificationDeliveryStatus = NotificationDeliveryStatus.PENDING
    merge_key: str
    requires_immediate_delivery: bool = False
