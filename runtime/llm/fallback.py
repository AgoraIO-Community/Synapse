from __future__ import annotations

import re

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
from runtime.protocols.tasks import Priority, TaskReference, TaskReferenceType


CONTROL_KEYWORDS = {
    "cancel": "cancel_task",
    "stop": "cancel_task",
    "pause": "pause_task",
    "resume": "resume_task",
    "continue": "resume_task",
    "retry": "retry_task",
}

UPDATE_KEYWORDS = ("update", "change", "instead", "modify", "make it", "use")


def _extract_explicit_task_id(text: str) -> str | None:
    match = re.search(r"\b(task_[a-zA-Z0-9]+)\b", text)
    return match.group(1) if match else None


def heuristic_interpretation(
    *,
    message_id: str,
    text: str,
    has_existing_tasks: bool,
) -> tuple[RoutingDecision, ActionBundle]:
    normalized = text.lower().strip()
    actions: list[RuntimeAction] = []
    explicit_task_id = _extract_explicit_task_id(normalized)
    task_ref = TaskReference(
        reference_type=TaskReferenceType.TASK_ID
        if explicit_task_id
        else TaskReferenceType.LATEST_ACTIVE,
        value=explicit_task_id,
    )

    priority = Priority.NORMAL
    needs_clarification = False
    clarification_reason = None

    for keyword, command_type in CONTROL_KEYWORDS.items():
        if keyword in normalized:
            priority = Priority.URGENT if command_type == "cancel_task" else Priority.HIGH
            if not has_existing_tasks:
                needs_clarification = True
                clarification_reason = "No active task is available to control."
            actions.append(
                RuntimeAction(
                    action_id=new_id("action"),
                    action_type=RuntimeActionType.CONTROL_TASK,
                    target_scope=TargetScope.EXISTING_TASK,
                    target_task_ref=task_ref,
                    payload={"command_type": command_type, "reason": text},
                    priority=priority,
                    execution_trigger=ExecutionTrigger.SOFT,
                    scope_of_effect=ScopeOfEffect.TASK,
                )
            )
            break

    if not actions and any(keyword in normalized for keyword in UPDATE_KEYWORDS):
        if not has_existing_tasks:
            needs_clarification = True
            clarification_reason = "The update refers to an existing task, but none is active."
        actions.append(
            RuntimeAction(
                action_id=new_id("action"),
                action_type=RuntimeActionType.UPDATE_TASK,
                target_scope=TargetScope.EXISTING_TASK,
                target_task_ref=task_ref,
                payload={"latest_instruction": text},
                priority=Priority.HIGH,
                execution_trigger=ExecutionTrigger.SOFT,
                scope_of_effect=ScopeOfEffect.TASK,
            )
        )

    if not actions:
        input_context = {
            "simulate_blocked": "need info" in normalized or "ask me" in normalized,
        }
        actions.append(
            RuntimeAction(
                action_id=new_id("action"),
                action_type=RuntimeActionType.CREATE_TASK,
                target_scope=TargetScope.NEW_TASK,
                payload={
                    "title": text[:80],
                    "goal": text,
                    "input_context": input_context,
                },
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.HARD,
                scope_of_effect=ScopeOfEffect.TASK,
            )
        )

    patch = ContextPatch(
        patch_id=new_id("patch"),
        scope=PatchScope.SESSION,
        producer="message_router",
        patch={"latest_user_goal": text},
    )
    actions.append(
        RuntimeAction(
            action_id=new_id("action"),
            action_type=RuntimeActionType.APPLY_CONTEXT_PATCH,
            target_scope=TargetScope.SESSION,
            payload=patch.model_dump(mode="json"),
            priority=Priority.NORMAL,
            execution_trigger=ExecutionTrigger.NONE,
            scope_of_effect=ScopeOfEffect.SESSION,
        )
    )

    decision = RoutingDecision(
        decision_id=new_id("decision"),
        message_id=message_id,
        conversation_action_enabled=True,
        task_action_enabled=True,
        context_action_enabled=True,
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
        priority_hint=priority,
        resolver_strategy=ResolverStrategy.IMPLICIT,
        confidence=0.75,
    )

    bundle = ActionBundle(
        bundle_id=new_id("bundle"),
        message_id=message_id,
        actions=actions,
    )
    return decision, bundle
