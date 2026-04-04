from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.infrastructure.time import utc_now


class Modality(StrEnum):
    TEXT = "text"
    VOICE_TRANSCRIPT = "voice_transcript"


class ConversationActionType(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    CLARIFY = "clarify"
    ASK_CONFIRMATION = "ask_confirmation"
    INFORM_PROGRESS = "inform_progress"
    INFORM_BLOCKED = "inform_blocked"
    INFORM_DONE = "inform_done"
    INFORM_FAILED = "inform_failed"
    INFORM_CANCELED = "inform_canceled"
    HOLD = "hold"


class Urgency(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class UserMessage(BaseModel):
    message_id: str
    session_id: str
    text: str
    modality: Modality = Modality.TEXT
    timestamp: Any = Field(default_factory=utc_now)
    turn_id: str | None = None
    interrupts_current_output: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationAction(BaseModel):
    action_id: str
    action_type: ConversationActionType
    target_task_id: str | None = None
    urgency: Urgency = Urgency.NORMAL
    reason: str | None = None
    render_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommunicationEvent(BaseModel):
    event_id: str
    session_id: str
    source: str = "communication_brain"
    action: ConversationAction
    timestamp: Any = Field(default_factory=utc_now)
