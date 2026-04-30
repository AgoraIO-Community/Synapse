from __future__ import annotations

from pydantic import BaseModel, Field

from newbro.protocol import SessionStatus


class ExecutorSession(BaseModel):
    session_id: str
    executor_type: str
    status: SessionStatus = SessionStatus.IDLE
    metadata: dict[str, object] = Field(default_factory=dict)
