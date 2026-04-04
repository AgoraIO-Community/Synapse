from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from runtime.infrastructure.time import utc_now


class TraceStage(StrEnum):
    API = "api"
    MESSAGE_INTERPRETER = "message_interpreter"
    ACTION_ROUTER = "action_router"
    INTERACTION_POLICY = "interaction_policy"
    RUNTIME_STATE = "runtime_state"
    TASK_GRAPH = "task_graph"
    EXECUTION_ORCHESTRATOR = "execution_orchestrator"
    EXECUTOR_ADAPTER = "executor_adapter"
    RESPONSE_GENERATOR = "response_generator"


class TraceEvent(BaseModel):
    trace_sequence: int
    trace_event_id: str
    session_id: str
    stage: TraceStage
    event_type: str
    source_module: str
    span_id: str | None = None
    parent_span_id: str | None = None
    related_message_id: str | None = None
    related_task_id: str | None = None
    timestamp: Any = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class TraceSnapshot(BaseModel):
    session_id: str
    recent_traces: list[TraceEvent] = Field(default_factory=list)
    last_trace_sequence: int = 0
    timestamp: Any = Field(default_factory=utc_now)
