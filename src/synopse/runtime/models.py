from __future__ import annotations

from pydantic import BaseModel, Field

from synopse.protocol import (
    ExecutionRun,
    ExecutionSession,
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
    mutations: list[TaskMutation] = Field(default_factory=list)
    commands: list[TaskCommand] = Field(default_factory=list)
    execution_sessions: list[ExecutionSession] = Field(default_factory=list)
    execution_runs: list[ExecutionRun] = Field(default_factory=list)
    bindings: list[SessionBinding] = Field(default_factory=list)
    summaries: list[TaskSummary] = Field(default_factory=list)
    recent_blackboard_writes: list[BlackboardWriteEvent] = Field(default_factory=list)
    conversation_history: list[ConversationHistoryEntryModel] = Field(default_factory=list)
