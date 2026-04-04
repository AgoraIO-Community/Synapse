from datetime import datetime, timezone

from runtime.infrastructure.ids import new_id
from runtime.protocols.runtime import ContextPatch, PatchScope
from runtime.protocols.tasks import ControlCommandType, Task, TaskStatus
from runtime.shared_blackboard.blackboard_state import BlackboardSessionState
from runtime.shared_blackboard.mutations import (
    append_message_history,
    apply_context_patch,
    apply_control,
    apply_task_update,
    get_message_history,
)


def test_apply_context_patch_updates_session_conversation_state():
    session = BlackboardSessionState(session_id="session_test")
    patch = ContextPatch(
        patch_id=new_id("patch"),
        scope=PatchScope.CONVERSATION,
        producer="test",
        patch={"latest_user_goal": "book a flight"},
    )
    apply_context_patch(session, patch)
    assert session.conversation_state["latest_user_goal"] == "book a flight"


def test_apply_task_update_stores_unknown_keys_in_input_context():
    task = Task(task_id="task_1", root_task_id="task_1", title="T", goal="G")
    apply_task_update(task, {"channel": "email"})
    assert task.input_context["channel"] == "email"


def test_apply_control_can_retry_blocked_task():
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="T",
        goal="G",
        status=TaskStatus.BLOCKED,
        block_reason="waiting",
    )
    apply_control(task, ControlCommandType.RETRY_TASK)
    assert task.status == TaskStatus.QUEUED
    assert task.block_reason is None


def test_append_message_history_keeps_last_thirty_messages():
    session = BlackboardSessionState(session_id="session_test")

    for index in range(35):
        append_message_history(
            session,
            role="user" if index % 2 == 0 else "assistant",
            text=f"message {index}",
            message_id=f"message_{index}",
        )

    history = get_message_history(session)

    assert len(history) == 30
    assert history[0]["message_id"] == "message_5"
    assert history[-1]["message_id"] == "message_34"
    assert isinstance(history[-1]["timestamp"], str)


def test_get_message_history_serializes_existing_datetime_timestamps():
    session = BlackboardSessionState(session_id="session_test")
    session.conversation_state["message_history"] = [
        {
            "role": "user",
            "text": "hello",
            "message_id": "message_1",
            "timestamp": datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc),
        }
    ]

    history = get_message_history(session)

    assert history == [
        {
            "role": "user",
            "text": "hello",
            "message_id": "message_1",
            "timestamp": "2026-04-04T12:00:00+00:00",
        }
    ]
