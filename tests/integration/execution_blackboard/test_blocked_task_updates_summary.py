import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.execution import ExecutionBrain
from synapse.executors.adapters.mock import MockExecutor
from synapse.executors.core import ExecutorRegistry
from synapse.protocol import Task, TaskStatus


@pytest.mark.anyio
async def test_blocked_task_updates_summary_and_user_input_flag():
    store = InMemoryBlackboard()
    registry = ExecutorRegistry()
    registry.register(MockExecutor())
    brain = ExecutionBrain(store, registry, worker_id="worker-1", default_executor_type="mock")
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Blocked task",
        goal="Blocked task",
        status=TaskStatus.QUEUED,
        preferred_executor="mock",
        metadata={"mock_behavior": "blocked", "mock_block_reason": "Need user input."},
    )
    await store.put_task(task)

    await brain.tick()

    saved_task = await store.get_task("task_1")
    assert saved_task is not None
    assert saved_task.status == TaskStatus.WAITING_USER_INPUT
    summary = await store.get_summary("task_1")
    assert summary is not None
    assert summary.needs_user_input is True
