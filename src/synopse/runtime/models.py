from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from synopse.protocol import (
    TaskExecutionMode,
    ExecutionRun,
    ExecutionSession,
    NotificationCandidate,
    SessionBinding,
    Task,
    TaskCommand,
    TaskMutation,
    TaskSummary,
)
from synopse.blackboard.store import BlackboardWriteEvent


class ConversationHistoryEntryModel(BaseModel):
    role: str
    text: str
    message_id: str


class SessionSnapshot(BaseModel):
    session_id: str
    tasks: list[Task] = Field(default_factory=list)
    execution_sessions: list[ExecutionSession] = Field(default_factory=list)
    execution_runs: list[ExecutionRun] = Field(default_factory=list)
    execution_modes: list[TaskExecutionMode] = Field(default_factory=list)
    bindings: list[SessionBinding] = Field(default_factory=list)
    summaries: list[TaskSummary] = Field(default_factory=list)
    notification_candidates: list[NotificationCandidate] = Field(default_factory=list)
 

class ConversationSnapshot(BaseModel):
    session_id: str
    conversation_history: list[ConversationHistoryEntryModel] = Field(default_factory=list)


class DebugSnapshot(BaseModel):
    session_id: str
    mutations: list[TaskMutation] = Field(default_factory=list)
    commands: list[TaskCommand] = Field(default_factory=list)
    recent_blackboard_writes: list[BlackboardWriteEvent] = Field(default_factory=list)


class SessionStreamEventBase(BaseModel):
    sequence: int
    type: str


class SnapshotStreamEvent(SessionStreamEventBase):
    type: Literal["snapshot"] = "snapshot"
    snapshot: SessionSnapshot


class ActionAcceptedStreamEvent(SessionStreamEventBase):
    type: Literal["action_accepted"] = "action_accepted"
    request_id: str
    action_type: str


class ActionRejectedStreamEvent(SessionStreamEventBase):
    type: Literal["action_rejected"] = "action_rejected"
    request_id: str
    action_type: str
    error_code: str
    message: str


class AssistantResponseStartedStreamEvent(SessionStreamEventBase):
    type: Literal["assistant_response_started"] = "assistant_response_started"
    request_id: str


class AssistantResponseDeltaStreamEvent(SessionStreamEventBase):
    type: Literal["assistant_response_delta"] = "assistant_response_delta"
    request_id: str
    delta: str


class AssistantResponseCompletedStreamEvent(SessionStreamEventBase):
    type: Literal["assistant_response_completed"] = "assistant_response_completed"
    request_id: str
    message_id: str
    reply_text: str
    conversational_act: str
    affected_task_ids: list[str] = Field(default_factory=list)


class AssistantResponseFailedStreamEvent(SessionStreamEventBase):
    type: Literal["assistant_response_failed"] = "assistant_response_failed"
    request_id: str
    message: str
