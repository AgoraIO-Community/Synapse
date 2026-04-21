from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .session import AgentResumeHandle


class ExecutorHostExecutor(BaseModel):
    executor_type: str
    supports_resume: bool = False
    supports_follow_up: bool = False
    supports_pause: bool = False
    supports_cancel: bool = True


class RegisterHostMessage(BaseModel):
    type: Literal["register_host"] = "register_host"
    host_id: str
    host_token: str
    executors: list[ExecutorHostExecutor] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class HeartbeatMessage(BaseModel):
    type: Literal["heartbeat"] = "heartbeat"
    host_id: str


class RunEventMessage(BaseModel):
    type: Literal["run_event"] = "run_event"
    run_id: str
    execution_session_id: str
    executor_type: str
    session_id: str
    event_type: Literal[
        "progress",
        "waiting_executor",
        "blocked",
        "completed",
        "failed",
        "cancelled",
    ]
    message: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    latest_resume_handle: AgentResumeHandle | None = None


class InteractionStateMessage(BaseModel):
    type: Literal["interaction_state"] = "interaction_state"
    run_id: str
    execution_session_id: str
    executor_type: str
    state: str
    prompt: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class HostStatusMessage(BaseModel):
    type: Literal["host_status"] = "host_status"
    host_id: str
    status: Literal["ready", "degraded"]
    metadata: dict[str, object] = Field(default_factory=dict)


class DispatchRunCommand(BaseModel):
    type: Literal["dispatch_run"] = "dispatch_run"
    run_id: str
    execution_session_id: str
    executor_type: str
    task_id: str
    title: str
    goal: str
    latest_instruction: str | None = None
    workspace_id: str | None = None
    task_metadata: dict[str, object] = Field(default_factory=dict)
    latest_resume_handle: AgentResumeHandle | None = None


class CancelRunCommand(BaseModel):
    type: Literal["cancel_run"] = "cancel_run"
    run_id: str
    execution_session_id: str
    mode: Literal["cancel", "pause"] = "cancel"


class SupplyInteractionResponseCommand(BaseModel):
    type: Literal["supply_interaction_response"] = "supply_interaction_response"
    interaction_request_id: str
    execution_session_id: str | None = None
    run_id: str | None = None
    action: Literal["approve", "deny", "answer", "confirm", "cancel"]
    answer_text: str | None = None
    native_response: dict[str, object] | None = None


class ReleaseRunCommand(BaseModel):
    type: Literal["release_run"] = "release_run"
    run_id: str
    execution_session_id: str


class AckMessage(BaseModel):
    type: Literal["ack"] = "ack"
    message_type: str
    ok: bool = True
    run_id: str | None = None
    detail: str | None = None
