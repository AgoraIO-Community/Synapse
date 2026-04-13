from __future__ import annotations

import pytest

from synapse.blackboard.backends import InMemoryBlackboard
from synapse.blackboard.queries import BlackboardQueryService
from synapse.protocol import Task, TaskCommand, TaskCommandType, TaskMutation, TaskStatus


@pytest.mark.anyio
async def test_query_service_lists_runnable_tasks():
    store = InMemoryBlackboard()
    query = BlackboardQueryService(store)
    created = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Created task",
        goal="Created task",
        status=TaskStatus.CREATED,
    )
    queued = Task(
        task_id="task_2",
        root_task_id="task_2",
        title="Queued task",
        goal="Queued task",
        status=TaskStatus.QUEUED,
    )
    running = Task(
        task_id="task_3",
        root_task_id="task_3",
        title="Running task",
        goal="Running task",
        status=TaskStatus.RUNNING,
    )
    for task in (created, queued, running):
        await store.put_task(task)

    runnable_ids = [task.task_id for task in await query.list_runnable_tasks()]
    assert runnable_ids == ["task_1", "task_2"]


@pytest.mark.anyio
async def test_query_service_returns_latest_mutation_and_command():
    store = InMemoryBlackboard()
    query = BlackboardQueryService(store)
    first_mutation = TaskMutation(
        mutation_id="mut_1",
        task_id="task_1",
        mutation_type="update",
        patch={"x": 1},
        created_by="communication_brain",
    )
    second_mutation = TaskMutation(
        mutation_id="mut_2",
        task_id="task_1",
        mutation_type="add_constraint",
        patch={"x": 2},
        created_by="communication_brain",
    )
    first_command = TaskCommand(
        command_id="cmd_1",
        task_id="task_1",
        command_type=TaskCommandType.PAUSE_TASK,
        created_by="communication_brain",
    )
    second_command = TaskCommand(
        command_id="cmd_2",
        task_id="task_1",
        command_type=TaskCommandType.CANCEL_TASK,
        created_by="communication_brain",
    )

    await store.append_mutation(first_mutation)
    await store.append_mutation(second_mutation)
    await store.append_command(first_command)
    await store.append_command(second_command)

    assert await query.get_latest_mutation("task_1") == second_mutation
    assert await query.get_latest_command("task_1") == second_command
