from __future__ import annotations

from pydantic import BaseModel, Field

from synopse.protocol import TaskCommandType
from synopse.runtime.models import SessionSnapshot


class SessionResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    text: str


class ToolInvocationSummary(BaseModel):
    tool_name: str
    args: dict[str, object] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    message_id: str
    reply_text: str
    conversational_act: str
    affected_task_ids: list[str] = Field(default_factory=list)
    tool_invocations: list[ToolInvocationSummary] = Field(default_factory=list)


class CommandRequest(BaseModel):
    command_type: TaskCommandType
    task_id: str | None = None
    reference: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    reason: str | None = None


class CommandResponse(BaseModel):
    command_id: str
    status: str = "accepted"
    affected_task_ids: list[str] = Field(default_factory=list)


__all__ = [
    "CommandRequest",
    "CommandResponse",
    "MessageRequest",
    "MessageResponse",
    "SessionResponse",
    "SessionSnapshot",
    "ToolInvocationSummary",
]
