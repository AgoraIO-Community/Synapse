from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.infrastructure.time import utc_now


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    PAUSED = "paused"
    CANCELED = "canceled"
    FAILED = "failed"
    DONE = "done"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskReferenceType(StrEnum):
    TASK_ID = "task_id"
    LATEST_ACTIVE = "latest_active"
    LATEST_CREATED = "latest_created"
    BY_ALIAS = "by_alias"
    BY_GOAL_MATCH = "by_goal_match"
    BY_RELATION = "by_relation"


class TaskReferenceRelation(StrEnum):
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    CURRENT = "current"


class TaskReference(BaseModel):
    reference_type: TaskReferenceType
    value: str | None = None
    relation: TaskReferenceRelation | None = None
    status_filter: list[str] = Field(default_factory=list)
    resolved_task_id: str | None = None
    confidence: float | None = None


class Artifact(BaseModel):
    artifact_id: str
    task_id: str
    artifact_type: str
    name: str
    mime_type: str | None = None
    uri: str | None = None
    inline_value: str | dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    task_id: str
    root_task_id: str
    parent_task_id: str | None = None
    title: str
    goal: str
    status: TaskStatus = TaskStatus.QUEUED
    priority: Priority = Priority.NORMAL
    interruptible: bool = True
    requires_confirmation: bool = False
    assigned_executor: str | None = None
    candidate_executors: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    depends_on_task_ids: list[str] = Field(default_factory=list)
    created_from_message_id: str | None = None
    latest_instruction: str | None = None
    input_context: dict[str, Any] = Field(default_factory=dict)
    output_summary: str | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    block_reason: str | None = None
    failure_reason: str | None = None
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)


class TaskMutationType(StrEnum):
    UPDATE = "update"
    REPLAN = "replan"
    ATTACH_CONTEXT = "attach_context"
    SET_PRIORITY = "set_priority"
    SET_EXECUTOR = "set_executor"


class IssuedBy(StrEnum):
    COMMUNICATION_BRAIN = "communication_brain"
    EXECUTION_BRAIN = "execution_brain"
    SYSTEM = "system"
    USER = "user"


class TaskMutation(BaseModel):
    mutation_id: str
    task_id: str
    mutation_type: TaskMutationType
    patch: dict[str, Any]
    issued_by: IssuedBy
    timestamp: Any = Field(default_factory=utc_now)


class ControlCommandType(StrEnum):
    PAUSE_TASK = "pause_task"
    RESUME_TASK = "resume_task"
    CANCEL_TASK = "cancel_task"
    RETRY_TASK = "retry_task"


class ControlCommand(BaseModel):
    command_id: str
    target_task_ref: TaskReference
    target_task_id: str | None = None
    command_type: ControlCommandType
    payload: dict[str, Any] = Field(default_factory=dict)
    issued_by: IssuedBy = IssuedBy.USER
    reason: str | None = None
    timestamp: Any = Field(default_factory=utc_now)
