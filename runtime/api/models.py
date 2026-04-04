from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from runtime.protocols.conversation import Modality
from runtime.protocols.tasks import ControlCommandType, TaskReference, TaskReferenceType


class SessionResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    text: str
    modality: Modality = Modality.TEXT
    interrupts_current_output: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    message_id: str
    routing_decision: dict[str, Any]
    action_bundle: dict[str, Any]


class CommandRequest(BaseModel):
    command_type: ControlCommandType
    target_task_id: str | None = None
    target_task_ref: TaskReference | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None

    def effective_reference(self) -> TaskReference:
        if self.target_task_ref is not None:
            return self.target_task_ref
        if self.target_task_id is not None:
            return TaskReference(
                reference_type=TaskReferenceType.TASK_ID,
                value=self.target_task_id,
            )
        return TaskReference(reference_type=TaskReferenceType.LATEST_ACTIVE)
