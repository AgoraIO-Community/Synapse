from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from runtime.infrastructure.ids import new_id
from runtime.protocols.runtime import (
    ActionBundle,
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
    conversation_action_enabled: bool = True
    task_action_enabled: bool = True
    context_action_enabled: bool = True
    needs_clarification: bool = False
    clarification_reason: str = ""
    priority_hint: Priority = Priority.NORMAL
    resolver_strategy: ResolverStrategy = ResolverStrategy.IMPLICIT
    confidence: float = 0.0


class InterpreterAction(StrictSchemaModel):
    action_id: str
    action_type: RuntimeActionType
    target_scope: TargetScope
    priority: Priority = Priority.NORMAL
    execution_trigger: ExecutionTrigger = ExecutionTrigger.NONE
    scope_of_effect: ScopeOfEffect = ScopeOfEffect.TASK

    target_task_reference_type: TaskReferenceType = TaskReferenceType.LATEST_ACTIVE
    target_task_reference_value: str = ""
    target_task_reference_relation: TaskReferenceRelation = TaskReferenceRelation.CURRENT
    target_task_status_filter: list[str] = Field(default_factory=list)

    title: str = ""
    goal: str = ""
    simulate_blocked: bool = False
    latest_instruction: str = ""
    command_type: ControlCommandType = ControlCommandType.PAUSE_TASK
    reason: str = ""
    latest_user_goal: str = ""


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
        reference_type=action.target_task_reference_type,
        value=action.target_task_reference_value or None,
        relation=action.target_task_reference_relation,
        status_filter=action.target_task_status_filter,
    )


def to_runtime_routing_decision(
    decision: InterpreterRoutingDecision,
) -> RoutingDecision:
    return RoutingDecision(
        decision_id=decision.decision_id,
        message_id=decision.message_id,
        conversation_action_enabled=decision.conversation_action_enabled,
        task_action_enabled=decision.task_action_enabled,
        context_action_enabled=decision.context_action_enabled,
        needs_clarification=decision.needs_clarification,
        clarification_reason=decision.clarification_reason or None,
        priority_hint=decision.priority_hint,
        resolver_strategy=decision.resolver_strategy,
        confidence=decision.confidence,
    )


def to_runtime_action(action: InterpreterAction) -> RuntimeAction:
    if action.action_type == RuntimeActionType.CREATE_TASK:
        payload = {
            "title": action.title,
            "goal": action.goal,
            "input_context": {
                "simulate_blocked": action.simulate_blocked,
            },
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
            payload={"latest_instruction": action.latest_instruction},
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
                "command_type": action.command_type.value,
                "reason": action.reason or None,
            },
            priority=action.priority,
            execution_trigger=action.execution_trigger,
            scope_of_effect=action.scope_of_effect,
        )

    patch = ContextPatch(
        patch_id=new_id("patch"),
        scope=PatchScope.SESSION,
        producer="action_router",
        patch={"latest_user_goal": action.latest_user_goal},
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
