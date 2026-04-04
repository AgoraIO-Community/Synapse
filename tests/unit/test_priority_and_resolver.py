from app.message_router.priorities import sort_actions
from app.message_router.resolver import resolve_task_reference
from app.protocols.runtime import ExecutionTrigger, RuntimeAction, RuntimeActionType, ScopeOfEffect, TargetScope
from app.protocols.tasks import Priority, Task, TaskReference, TaskReferenceType, TaskStatus
from app.shared_blackboard.models import SessionState


def test_control_actions_sort_ahead_of_new_tasks():
    actions = [
        RuntimeAction(
            action_id="a1",
            action_type=RuntimeActionType.CREATE_TASK,
            target_scope=TargetScope.NEW_TASK,
            priority=Priority.NORMAL,
            execution_trigger=ExecutionTrigger.HARD,
            scope_of_effect=ScopeOfEffect.TASK,
        ),
        RuntimeAction(
            action_id="a2",
            action_type=RuntimeActionType.CONTROL_TASK,
            target_scope=TargetScope.EXISTING_TASK,
            priority=Priority.URGENT,
            payload={"command_type": "cancel_task"},
            execution_trigger=ExecutionTrigger.SOFT,
            scope_of_effect=ScopeOfEffect.TASK,
        ),
    ]
    ordered = sort_actions(actions)
    assert ordered[0].action_id == "a2"


def test_resolve_latest_active_prefers_running_task():
    older = Task(
        task_id="task_old",
        root_task_id="task_old",
        title="Old",
        goal="Old goal",
        status=TaskStatus.DONE,
    )
    newer = Task(
        task_id="task_new",
        root_task_id="task_new",
        title="New",
        goal="New goal",
        status=TaskStatus.RUNNING,
    )
    session = SessionState(session_id="session_test", task_registry={older.task_id: older, newer.task_id: newer})
    resolved = resolve_task_reference(
        session, TaskReference(reference_type=TaskReferenceType.LATEST_ACTIVE)
    )
    assert resolved is not None
    assert resolved.task_id == "task_new"
