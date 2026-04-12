from __future__ import annotations

import pytest

from synapse.blackboard.backends import InMemoryBlackboard
from synapse.protocol import (
    BindingStatus,
    ExecutionMode,
    ExecutionRun,
    ExecutionSession,
    NotificationCandidate,
    NotificationCandidateType,
    NotificationDeliveryStatus,
    NotificationPriority,
    SessionBinding,
    Task,
    TaskCommand,
    TaskCommandType,
    TaskExecutionMode,
    TaskMutation,
    TaskStatus,
    TaskSummary,
)


@pytest.mark.anyio
async def test_memory_blackboard_round_trip_for_core_objects():
    store = InMemoryBlackboard()

    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Draft email",
        goal="Draft a reply",
    )
    session = ExecutionSession(
        execution_session_id="sess_1",
        task_id="task_1",
        base_executor_id="codex",
    )
    run = ExecutionRun(
        run_id="run_1",
        task_id="task_1",
        execution_session_id="sess_1",
        executor_type="codex",
    )
    binding = SessionBinding(
        task_id="task_1",
        execution_session_id="sess_1",
        session_id="agent_session_1",
        binding_status=BindingStatus.ACTIVE,
    )
    summary = TaskSummary(
        task_id="task_1",
        conversational_summary="I am working on it.",
    )
    execution_mode = TaskExecutionMode(
        task_id="task_1",
        mode=ExecutionMode.UNDECIDED,
    )
    candidate = NotificationCandidate(
        candidate_id="notif_1",
        task_id="task_1",
        candidate_type=NotificationCandidateType.COMPLETED,
        priority=NotificationPriority.P2,
        summary_short="Task completed.",
        created_at="2026-04-06T00:00:00+00:00",
        delivery_status=NotificationDeliveryStatus.PENDING,
        merge_key="completed_digest",
    )

    await store.put_task(task)
    await store.put_session(session)
    await store.put_run(run)
    await store.put_binding(binding)
    await store.put_summary(summary)
    await store.put_execution_mode(execution_mode)
    await store.put_notification_candidate(candidate)

    assert await store.get_task("task_1") == task
    assert await store.get_session("sess_1") == session
    assert await store.get_run("run_1") == run
    assert await store.get_binding("task_1") == binding
    assert await store.get_summary("task_1") == summary
    assert await store.get_execution_mode("task_1") == execution_mode
    assert await store.get_notification_candidate("notif_1") == candidate


@pytest.mark.anyio
async def test_memory_blackboard_appends_mutations_and_bumps_task_revision():
    store = InMemoryBlackboard()
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Investigate issue",
        goal="Investigate the issue",
    )
    await store.put_task(task)

    mutation = TaskMutation(
        mutation_id="mut_1",
        task_id="task_1",
        mutation_type="add_constraint",
        patch={"tone": "casual"},
        created_by="communication_brain",
    )

    await store.append_mutation(mutation)

    saved_task = await store.get_task("task_1")
    assert saved_task is not None
    assert saved_task.task_revision == 1
    assert await store.list_mutations("task_1") == [mutation]
    assert await store.list_all_mutations() == [mutation]


@pytest.mark.anyio
async def test_memory_blackboard_appends_commands_in_order():
    store = InMemoryBlackboard()
    command_one = TaskCommand(
        command_id="cmd_1",
        task_id="task_1",
        command_type=TaskCommandType.PAUSE_TASK,
        created_by="communication_brain",
    )
    command_two = TaskCommand(
        command_id="cmd_2",
        task_id="task_1",
        command_type=TaskCommandType.CANCEL_TASK,
        created_by="communication_brain",
    )

    await store.append_command(command_one)
    await store.append_command(command_two)

    assert await store.list_commands("task_1") == [command_one, command_two]
    assert await store.list_all_commands() == [command_one, command_two]


@pytest.mark.anyio
async def test_memory_blackboard_notifies_subscribers_on_writes():
    store = InMemoryBlackboard()
    queue = store.subscribe()
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Check prices",
        goal="Check prices",
        status=TaskStatus.QUEUED,
    )

    await store.put_task(task)
    event = await queue.get()

    assert event.kind.value == "task"
    assert event.task_id == "task_1"
    recent_writes = await store.list_recent_writes()
    assert recent_writes[-1].task_id == "task_1"

    store.unsubscribe(queue)
