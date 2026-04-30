from __future__ import annotations

from pydantic import BaseModel

from .enums import ConversationEffect, InterruptionType


class Interruption(BaseModel):
    interruption_id: str
    task_id: str | None = None
    interruption_type: InterruptionType
    execution_effect: str = "none"
    conversational_effect: ConversationEffect = ConversationEffect.STOP_OUTPUT
