import pytest

from newbro.blackboard import InMemoryBlackboard
from newbro.execution import ExecutionBrain
from newbro.executors.adapters.mock import MockExecutor
from newbro.executors.core import ExecutorRegistry
from newbro.protocol import Task, TaskStatus


@pytest.mark.anyio
async def test_execution_brain_tick_claims_runs_and_completes():
    store = InMemoryBlackboard()
    registry = ExecutorRegistry()
    registry.register(MockExecutor())
    brain = ExecutionBrain(store, registry, worker_id="worker-1", default_executor_type="mock")
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Complete task",
        goal="Complete task",
        status=TaskStatus.QUEUED,
        preferred_executor="mock",
    )
    await store.put_task(task)

    run_ids = await brain.tick()

    assert len(run_ids) == 1
    saved_task = await store.get_task("task_1")
    assert saved_task is not None
    assert saved_task.status == TaskStatus.COMPLETED
    summary = await store.get_summary("task_1")
    assert summary is not None
    assert summary.latest_user_visible_status == "completed"
    execution_mode = await store.get_execution_mode("task_1")
    assert execution_mode is not None
    assert execution_mode.mode.value == "lightweight"


@pytest.mark.anyio
async def test_execution_brain_marks_unknown_executor_tasks_failed():
    store = InMemoryBlackboard()
    registry = ExecutorRegistry()
    registry.register(MockExecutor())
    brain = ExecutionBrain(store, registry, worker_id="worker-1", default_executor_type="mock")
    task = Task(
        task_id="task_bad",
        root_task_id="task_bad",
        title="Bad executor task",
        goal="Bad executor task",
        status=TaskStatus.QUEUED,
        preferred_executor="User",
    )
    await store.put_task(task)

    run_ids = await brain.tick()

    assert run_ids == []
    saved_task = await store.get_task("task_bad")
    assert saved_task is not None
    assert saved_task.status == TaskStatus.FAILED
    summary = await store.get_summary("task_bad")
    assert summary is not None
    assert summary.latest_user_visible_status == "failed"
    assert "Unknown executor 'User'" in str(summary.operational_summary)
