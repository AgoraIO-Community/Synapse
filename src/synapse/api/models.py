from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from synapse.observability.schema import DiagnosticEvent
from synapse.protocol import ExecutorNodeCredentialIssue, ExecutorNodeRecord, TaskCommandType
from synapse.runtime.models import SessionSnapshot


class SessionResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    text: str
    source: Literal["user", "connector"] = "user"


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


class ResolveInteractionRequest(BaseModel):
    action: Literal["approve", "deny", "answer", "confirm", "cancel"]
    answer_text: str | None = None
    option_id: str | None = None
    reason: str | None = None


class ResolveInteractionRequestResponse(BaseModel):
    request_id: str
    status: str = "accepted"
    affected_task_ids: list[str] = Field(default_factory=list)


class SendMessageSocketAction(BaseModel):
    type: Literal["send_message"] = "send_message"
    request_id: str
    text: str
    source: Literal["user", "connector"] = "user"
    target_persona_id: str | None = None


class SendCommandSocketAction(BaseModel):
    type: Literal["send_command"] = "send_command"
    request_id: str
    command_type: TaskCommandType
    task_id: str | None = None
    reference: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    reason: str | None = None


class ResolveInteractionRequestSocketAction(BaseModel):
    type: Literal["resolve_interaction_request"] = "resolve_interaction_request"
    request_id: str
    interaction_request_id: str
    action: Literal["approve", "deny", "answer", "confirm", "cancel"]
    answer_text: str | None = None
    option_id: str | None = None
    reason: str | None = None


class DiagnosticTimelineResponse(BaseModel):
    events: list[DiagnosticEvent] = Field(default_factory=list)


class PersonaCreateRequest(BaseModel):
    name: str
    avatar: str = ""
    base_prompt: str = ""
    executor_node_id: str | None = None


class PersonaUpdateRequest(BaseModel):
    name: str | None = None
    avatar: str | None = None
    base_prompt: str | None = None
    executor_node_id: str | None = None


class ExecutorNodeCreateRequest(BaseModel):
    name: str
    enabled_executors: list[str] = Field(default_factory=list)


class ExecutorNodeUpdateRequest(BaseModel):
    name: str | None = None
    enabled_executors: list[str] | None = None


__all__ = [
    "CommandRequest",
    "CommandResponse",
    "DiagnosticTimelineResponse",
    "ExecutorNodeCreateRequest",
    "ExecutorNodeCredentialIssue",
    "ExecutorNodeRecord",
    "ExecutorNodeUpdateRequest",
    "MessageRequest",
    "MessageResponse",
    "ResolveInteractionRequest",
    "ResolveInteractionRequestResponse",
    "ResolveInteractionRequestSocketAction",
    "SendCommandSocketAction",
    "SendMessageSocketAction",
    "SessionResponse",
    "SessionSnapshot",
    "ToolInvocationSummary",
]
