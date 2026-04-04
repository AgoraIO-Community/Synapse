from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from runtime.infrastructure.ids import new_id
from runtime.protocols.runtime import (
    ActionBundle,
    ConversationMode,
    ContextPatch,
    ExecutionTrigger,
    PatchScope,
    ResolverStrategy,
    RoutingDecision,
    RuntimeAction,
    RuntimeActionType,
    ScopeOfEffect,
    TargetScope,
)
from runtime.protocols.tasks import (
    ControlCommandType,
    Priority,
    TaskReference,
    TaskReferenceRelation,
    TaskReferenceType,
)


class StrictSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterpreterRoutingDecision(StrictSchemaModel):
    decision_id: str
    message_id: str
    conversation_mode: ConversationMode = ConversationMode.TASK
    needs_clarification: bool = False
    clarification_reason: str | None = None
    priority_hint: Priority = Priority.NORMAL
    resolver_strategy: ResolverStrategy = ResolverStrategy.IMPLICIT


class InterpreterAction(StrictSchemaModel):
    action_id: str
    action_type: RuntimeActionType
    target_scope: TargetScope
    priority: Priority = Priority.NORMAL
    execution_trigger: ExecutionTrigger = ExecutionTrigger.NONE
    scope_of_effect: ScopeOfEffect = ScopeOfEffect.TASK

    target_task_reference_type: TaskReferenceType | None = None
    target_task_reference_value: str | None = None
    target_task_reference_relation: TaskReferenceRelation | None = None
    target_task_status_filter: list[str] = Field(default_factory=list)

    title: str | None = None
    goal: str | None = None
    latest_instruction: str | None = None
    command_type: ControlCommandType | None = None
    reason: str | None = None
    latest_user_goal: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_and_validate(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        for key in (
            "title",
            "goal",
            "latest_instruction",
            "reason",
            "latest_user_goal",
        ):
            value = normalized.get(key)
            if isinstance(value, str):
                stripped = value.strip()
                normalized[key] = stripped or None

        if normalized.get("action_type") in {
            RuntimeActionType.CREATE_TASK,
            RuntimeActionType.CREATE_TASK.value,
        }:
            goal = normalized.get("goal")
            if goal is None:
                raise ValueError("create_task requires a non-empty goal.")

            if "title" in normalized and data.get("title") is not None and normalized.get("title") is None:
                raise ValueError("create_task title must be non-empty when provided.")

        return normalized


class InterpreterActionBundle(StrictSchemaModel):
    bundle_id: str
    message_id: str
    actions: list[InterpreterAction]


class InterpretationEnvelope(StrictSchemaModel):
    routing_decision: InterpreterRoutingDecision
    action_bundle: InterpreterActionBundle


def _to_runtime_task_reference(action: InterpreterAction) -> TaskReference | None:
    if action.target_scope != TargetScope.EXISTING_TASK:
        return None
    return TaskReference(
        reference_type=action.target_task_reference_type or TaskReferenceType.LATEST_ACTIVE,
        value=action.target_task_reference_value,
        relation=action.target_task_reference_relation or TaskReferenceRelation.CURRENT,
        status_filter=action.target_task_status_filter,
    )


def to_runtime_routing_decision(
    decision: InterpreterRoutingDecision,
) -> RoutingDecision:
    return RoutingDecision(
        decision_id=decision.decision_id,
        message_id=decision.message_id,
        conversation_action_enabled=True,
        task_action_enabled=decision.conversation_mode == ConversationMode.TASK,
        context_action_enabled=True,
        conversation_mode=decision.conversation_mode,
        needs_clarification=decision.needs_clarification,
        clarification_reason=decision.clarification_reason,
        priority_hint=decision.priority_hint,
        resolver_strategy=decision.resolver_strategy,
        confidence=None,
    )


def _create_task_input_context(goal: str) -> dict[str, bool]:
    goal_text = goal.lower()
    return {
        "simulate_blocked": "need info" in goal_text or "ask me" in goal_text,
        "requires_executor_capability": True,
    }


def to_runtime_action(action: InterpreterAction) -> RuntimeAction:
    if action.action_type == RuntimeActionType.CREATE_TASK:
        goal = (action.goal or "").strip()
        if not goal:
            raise ValueError("create_task requires a non-empty goal.")
        title = action.title.strip() if action.title else goal[:80]
        if not title:
            raise ValueError("create_task requires a non-empty title.")
        payload = {
            "title": title,
            "goal": goal,
            "input_context": _create_task_input_context(goal),
        }
        return RuntimeAction(
            action_id=action.action_id,
            action_type=RuntimeActionType.CREATE_TASK,
            target_scope=TargetScope.NEW_TASK,
            payload=payload,
            priority=action.priority,
            execution_trigger=action.execution_trigger,
            scope_of_effect=action.scope_of_effect,
        )

    if action.action_type == RuntimeActionType.UPDATE_TASK:
        return RuntimeAction(
            action_id=action.action_id,
            action_type=RuntimeActionType.UPDATE_TASK,
            target_scope=TargetScope.EXISTING_TASK,
            target_task_ref=_to_runtime_task_reference(action),
            payload={"latest_instruction": action.latest_instruction or ""},
            priority=action.priority,
            execution_trigger=action.execution_trigger,
            scope_of_effect=action.scope_of_effect,
        )

    if action.action_type == RuntimeActionType.CONTROL_TASK:
        return RuntimeAction(
            action_id=action.action_id,
            action_type=RuntimeActionType.CONTROL_TASK,
            target_scope=TargetScope.EXISTING_TASK,
            target_task_ref=_to_runtime_task_reference(action),
            payload={
                "command_type": (action.command_type or ControlCommandType.CANCEL_TASK).value,
                "reason": action.reason,
            },
            priority=action.priority,
            execution_trigger=action.execution_trigger,
            scope_of_effect=action.scope_of_effect,
        )

    patch = ContextPatch(
        patch_id=new_id("patch"),
        scope=PatchScope.SESSION,
        producer="action_router",
        patch={"latest_user_goal": action.latest_user_goal or ""},
    )
    return RuntimeAction(
        action_id=action.action_id,
        action_type=RuntimeActionType.APPLY_CONTEXT_PATCH,
        target_scope=TargetScope.SESSION,
        payload=patch.model_dump(mode="json"),
        priority=action.priority,
        execution_trigger=action.execution_trigger,
        scope_of_effect=action.scope_of_effect,
    )


def to_runtime_action_bundle(bundle: InterpreterActionBundle) -> ActionBundle:
    return ActionBundle(
        bundle_id=bundle.bundle_id,
        message_id=bundle.message_id,
        actions=[to_runtime_action(action) for action in bundle.actions],
    )
