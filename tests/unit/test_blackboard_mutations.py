from app.infrastructure.ids import new_id
from app.protocols.runtime import ContextPatch, PatchScope
from app.protocols.tasks import ControlCommandType, Task, TaskStatus
from app.shared_blackboard.models import SessionState
from app.shared_blackboard.mutations import apply_context_patch, apply_control, apply_task_update


def test_apply_context_patch_updates_session_conversation_state():
    session = SessionState(session_id="session_test")
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
