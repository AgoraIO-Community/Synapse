import pytest

from runtime.execution_brain.task_graph import build_task
from runtime.protocols.runtime import (
    ExecutionTrigger,
    RuntimeAction,
    RuntimeActionType,
    ScopeOfEffect,
    TargetScope,
)


def make_create_task_action(*, input_context: dict | None = None) -> RuntimeAction:
    return RuntimeAction(
        action_id="action_1",
        action_type=RuntimeActionType.CREATE_TASK,
        target_scope=TargetScope.NEW_TASK,
        payload={
            "title": "Check CPU usage",
            "goal": "Check CPU usage",
            "input_context": input_context or {},
        },
        execution_trigger=ExecutionTrigger.HARD,
        scope_of_effect=ScopeOfEffect.TASK,
    )


def test_build_task_defaults_to_executor_requirement() -> None:
    task = build_task(
        make_create_task_action(),
        message_id="message_1",
        executor_id="mock_executor",
    )

    assert task.input_context["requires_executor_capability"] is True


def test_build_task_preserves_explicit_executor_requirement_override() -> None:
    task = build_task(
        make_create_task_action(input_context={"requires_executor_capability": False}),
        message_id="message_1",
        executor_id="mock_executor",
    )

    assert task.input_context["requires_executor_capability"] is False


def test_build_task_rejects_empty_goal() -> None:
    action = make_create_task_action()
    action.payload["goal"] = "   "

    with pytest.raises(ValueError, match="non-empty goal"):
        build_task(
            action,
            message_id="message_1",
            executor_id="mock_executor",
        )


def test_build_task_rejects_empty_title() -> None:
    action = make_create_task_action()
    action.payload["title"] = ""

    with pytest.raises(ValueError, match="non-empty title"):
        build_task(
            action,
            message_id="message_1",
            executor_id="mock_executor",
        )
