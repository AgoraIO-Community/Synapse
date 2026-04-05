from __future__ import annotations

from pydantic import BaseModel


class AssignmentLease(BaseModel):
    task_id: str
    claimed_by: str
    claim_expires_at: str
