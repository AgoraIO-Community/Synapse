from __future__ import annotations

import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.blackboard.store import BlackboardWriteEvent, BlackboardWriteKind
from synapse.interaction import InteractionManager
from synapse.protocol import (
    ExecutionRun,
    InteractionRequestKind,
    InteractionRequestStatus,
    RunStatus,
    Task,
    TaskSummary,
)


@pytest.mark.anyio
async def test_interaction_manager_builds_permission_request_from_blocked_run_metadata():
    store = InMemoryBlackboard()
    manager = InteractionManager(store)
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Permission task",
        goal="Permission task",
    )
    run = ExecutionRun(
        run_id="run-1",
        task_id="task-1",
        execution_session_id="exec-1",
        executor_type="codex",
        status=RunStatus.BLOCKED,
        block_reason="Allow network access?",
        metadata={"blocked_event": {"interaction_kind": "permission"}},
    )
    await store.put_task(task)
    await store.put_run(run)

    handled = await manager.handle_blackboard_write(
        BlackboardWriteEvent(
            kind=BlackboardWriteKind.RUN,
            entity_id="run-1",
            task_id="task-1",
        )
    )

    requests = await store.list_interaction_requests()
    items = await store.list_attention_items()
    assert handled is True
    assert len(requests) == 1
    assert requests[0].kind == InteractionRequestKind.PERMISSION
    assert requests[0].available_actions == ["approve", "deny"]
    assert len(items) == 1
    assert items[0].request_id == requests[0].request_id


@pytest.mark.anyio
async def test_interaction_manager_suppresses_duplicate_pending_request_for_same_run():
    store = InMemoryBlackboard()
    manager = InteractionManager(store)
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Blocked task",
        goal="Blocked task",
    )
    run = ExecutionRun(
        run_id="run-1",
        task_id="task-1",
        execution_session_id="exec-1",
        executor_type="codex",
        status=RunStatus.BLOCKED,
        block_reason="Need confirmation?",
    )
    await store.put_task(task)
    await store.put_run(run)

    first = await manager.handle_blackboard_write(
        BlackboardWriteEvent(kind=BlackboardWriteKind.RUN, entity_id="run-1", task_id="task-1")
    )
    second = await manager.handle_blackboard_write(
        BlackboardWriteEvent(kind=BlackboardWriteKind.RUN, entity_id="run-1", task_id="task-1")
    )

    assert first is True
    assert second is False
    assert len(await store.list_interaction_requests()) == 1


@pytest.mark.anyio
async def test_interaction_manager_builds_request_from_needs_input_summary():
    store = InMemoryBlackboard()
    manager = InteractionManager(store)
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Input task",
        goal="Input task",
    )
    summary = TaskSummary(
        task_id="task-1",
        conversational_summary="I need one more detail.",
        latest_user_visible_status="waiting_user_input",
        needs_user_input=True,
    )
    await store.put_task(task)
    await store.put_summary(summary)

    handled = await manager.handle_blackboard_write(
        BlackboardWriteEvent(kind=BlackboardWriteKind.SUMMARY, entity_id="task-1", task_id="task-1")
    )

    requests = await store.list_interaction_requests()
    assert handled is True
    assert len(requests) == 1
    assert requests[0].prompt == "I need one more detail."


@pytest.mark.anyio
async def test_interaction_manager_resolve_answer_marks_request_and_returns_follow_up_instruction():
    store = InMemoryBlackboard()
    manager = InteractionManager(store)
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Question task",
        goal="Question task",
    )
    run = ExecutionRun(
        run_id="run-1",
        task_id="task-1",
        execution_session_id="exec-1",
        executor_type="codex",
        status=RunStatus.BLOCKED,
        block_reason="Which project name should I use?",
    )
    await store.put_task(task)
    await store.put_run(run)
    await manager.handle_blackboard_write(
        BlackboardWriteEvent(kind=BlackboardWriteKind.RUN, entity_id="run-1", task_id="task-1")
    )
    request = (await store.list_interaction_requests())[0]

    resolution = await manager.resolve_request(
        request.request_id,
        action="answer",
        answer_text="Use Synopse",
    )

    updated = await store.get_interaction_request(request.request_id)
    attention = (await store.list_attention_items())[0]
    assert resolution.request.status == InteractionRequestStatus.ANSWERED
    assert updated is not None and updated.status == InteractionRequestStatus.ANSWERED
    assert "Use Synopse" in resolution.follow_up_instruction
    assert attention.status.value == "acted"


@pytest.mark.anyio
async def test_interaction_manager_rejects_invalid_resolution_action():
    store = InMemoryBlackboard()
    manager = InteractionManager(store)
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Permission task",
        goal="Permission task",
    )
    run = ExecutionRun(
        run_id="run-1",
        task_id="task-1",
        execution_session_id="exec-1",
        executor_type="codex",
        status=RunStatus.BLOCKED,
        block_reason="Allow network access?",
        metadata={"blocked_event": {"interaction_kind": "permission"}},
    )
    await store.put_task(task)
    await store.put_run(run)
    await manager.handle_blackboard_write(
        BlackboardWriteEvent(kind=BlackboardWriteKind.RUN, entity_id="run-1", task_id="task-1")
    )
    request = (await store.list_interaction_requests())[0]

    with pytest.raises(ValueError, match="not allowed"):
        await manager.resolve_request(request.request_id, action="answer", answer_text="yes")
