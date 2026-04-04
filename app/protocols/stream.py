from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.infrastructure.time import utc_now
from app.protocols.conversation import ConversationAction
from app.protocols.tasks import Task


class StreamCategory(StrEnum):
    COMMUNICATION = "communication"
    TASK = "task"
    EXECUTION = "execution"
    CONTEXT = "context"
    SYSTEM = "system"


class StreamEvent(BaseModel):
    sequence: int
    stream_event_id: str
    session_id: str
    category: StreamCategory
    event_type: str
    source: str
    related_task_id: str | None = None
    related_message_id: str | None = None
    timestamp: Any = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionSnapshot(BaseModel):
    session_id: str
    conversation_state: dict[str, Any] = Field(default_factory=dict)
    task_registry: list[Task] = Field(default_factory=list)
    strategy_state: dict[str, Any] = Field(default_factory=dict)
    pending_clarifications: list[ConversationAction] = Field(default_factory=list)
    last_sequence: int = 0
    timestamp: Any = Field(default_factory=utc_now)
