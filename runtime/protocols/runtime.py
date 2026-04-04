from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from runtime.infrastructure.time import utc_now
from runtime.protocols.tasks import Priority, TaskReference


class ResolverStrategy(StrEnum):
    IMPLICIT = "implicit"
    DIRECT_ID = "direct_id"


class ConversationMode(StrEnum):
    TASK = "task"
    CONVERSATION_ONLY = "conversation_only"
    CLARIFICATION = "clarification"


class TargetScope(StrEnum):
    NEW_TASK = "new_task"
    EXISTING_TASK = "existing_task"
    SESSION = "session"
    CONVERSATION = "conversation"
    STRATEGY = "strategy"


class RuntimeActionType(StrEnum):
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    CONTROL_TASK = "control_task"
    APPLY_CONTEXT_PATCH = "apply_context_patch"
    EMIT_CONVERSATION_ACTION = "emit_conversation_action"


class ExecutionTrigger(StrEnum):
    HARD = "hard"
    SOFT = "soft"
    DEFERRED = "deferred"
    NONE = "none"


class ScopeOfEffect(StrEnum):
    TASK = "task"
    SESSION = "session"
    CONVERSATION = "conversation"


class ActionRelationType(StrEnum):
    SAME_TARGET = "same_target"
    DEPENDS_ON = "depends_on"
    PRECEDES = "precedes"
    BLOCKS = "blocks"


class RoutingDecision(BaseModel):
    decision_id: str
    message_id: str
    conversation_action_enabled: bool = True
    task_action_enabled: bool = True
    context_action_enabled: bool = True
    conversation_mode: ConversationMode = ConversationMode.TASK
    needs_clarification: bool = False
    clarification_reason: str | None = None
    priority_hint: Priority = Priority.NORMAL
    resolver_strategy: ResolverStrategy = ResolverStrategy.IMPLICIT
    confidence: float | None = None


class RuntimeAction(BaseModel):
    action_id: str
    action_type: RuntimeActionType
    target_scope: TargetScope
    target_task_ref: TaskReference | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    execution_trigger: ExecutionTrigger = ExecutionTrigger.NONE
    scope_of_effect: ScopeOfEffect = ScopeOfEffect.TASK


class ActionRelation(BaseModel):
    from_action_id: str
    to_action_id: str
    relation: ActionRelationType


class ActionBundle(BaseModel):
    bundle_id: str
    message_id: str
    actions: list[RuntimeAction]
    relations: list[ActionRelation] = Field(default_factory=list)


class PatchFormat(StrEnum):
    JSON_MERGE = "json_merge"


class PatchScope(StrEnum):
    SESSION = "session"
    CONVERSATION = "conversation"
    TASK = "task"
    STRATEGY = "strategy"
    USER = "user"


class ContextPatch(BaseModel):
    patch_id: str
    patch_format: PatchFormat = PatchFormat.JSON_MERGE
    scope: PatchScope
    applies_to_task_id: str | None = None
    producer: str
    patch: dict[str, Any]
    timestamp: Any = Field(default_factory=utc_now)
