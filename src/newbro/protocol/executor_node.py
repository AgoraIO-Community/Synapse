from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .session import AgentResumeHandle


class ExecutorNodeExecutor(BaseModel):
    executor_type: str
    supports_resume: bool = False
    supports_follow_up: bool = False
    supports_pause: bool = False
    supports_cancel: bool = True


class ExecutorNodeRecord(BaseModel):
    node_id: str
    name: str
    enabled_executors: list[str] = Field(default_factory=list)
    acpx_agent: str | None = None
    connected_executors: list[str] = Field(default_factory=list)
    connection_status: Literal["connected", "disconnected"] = "disconnected"
    token_hint: str | None = None
    last_connected_at: str | None = None
    last_seen_at: str | None = None


class ExecutorNodeCredentialIssue(BaseModel):
    node: ExecutorNodeRecord
    token: str


class RegisterNodeMessage(BaseModel):
    type: Literal["register_node"] = "register_node"
    node_id: str
    token: str
    executors: list[ExecutorNodeExecutor] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


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


class NodeStatusMessage(BaseModel):
    type: Literal["node_status"] = "node_status"
    node_id: str
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
