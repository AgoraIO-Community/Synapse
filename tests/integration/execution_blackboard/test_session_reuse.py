import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.execution import ExecutionBrain
from synopse.executor_adapters.mock import MockExecutor
from synopse.executor_core import ExecutorRegistry
from synopse.protocol import Task, TaskStatus


@pytest.mark.anyio
async def test_session_is_reused_for_same_task_across_runs():
    store = InMemoryBlackboard()
    registry = ExecutorRegistry()
    registry.register(MockExecutor())
    brain = ExecutionBrain(store, registry, worker_id="worker-1")
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Reusable session task",
        goal="Reusable session task",
        status=TaskStatus.QUEUED,
        preferred_executor="mock",
    )
    await store.put_task(task)

    await brain.tick()
    sessions_after_first = await store.list_sessions()
    saved_task = await store.get_task("task_1")
    assert saved_task is not None
    saved_task.status = TaskStatus.QUEUED
    await store.put_task(saved_task)

    await brain.tick()
    sessions_after_second = await store.list_sessions()
    runs = await store.list_runs()

    assert len(sessions_after_first) == 1
    assert len(sessions_after_second) == 1
    assert len(runs) == 2
