import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.execution import ExecutionModeManager
from synapse.protocol import ExecutionMode, RunStatus


@pytest.mark.anyio
async def test_mode_manager_initializes_tasks_as_undecided():
    store = InMemoryBlackboard()
    manager = ExecutionModeManager(threshold_seconds=30.0)

    projection = await manager.initialize_task_mode(store, "task-1")

    assert projection.mode == ExecutionMode.UNDECIDED
    assert projection.elapsed_seconds == 0.0


@pytest.mark.anyio
async def test_mode_manager_marks_short_terminal_run_as_lightweight():
    store = InMemoryBlackboard()
    manager = ExecutionModeManager(threshold_seconds=30.0)

    projection = await manager.classify(
        store,
        task_id="task-1",
        run_id="run-1",
        run_status=RunStatus.COMPLETED,
        elapsed_seconds=12.0,
    )

    assert projection.mode == ExecutionMode.LIGHTWEIGHT
    assert projection.decided_from_run_id == "run-1"


@pytest.mark.anyio
async def test_mode_manager_marks_long_run_as_managed_and_never_downgrades():
    store = InMemoryBlackboard()
    manager = ExecutionModeManager(threshold_seconds=30.0)

    projection = await manager.classify(
        store,
        task_id="task-1",
        run_id="run-1",
        run_status=RunStatus.RUNNING,
        elapsed_seconds=31.0,
    )
    assert projection.mode == ExecutionMode.MANAGED

    downgraded = await manager.classify(
        store,
        task_id="task-1",
        run_id="run-2",
        run_status=RunStatus.COMPLETED,
        elapsed_seconds=5.0,
    )
    assert downgraded.mode == ExecutionMode.MANAGED


@pytest.mark.anyio
async def test_mode_manager_allows_lightweight_to_upgrade_to_managed():
    store = InMemoryBlackboard()
    manager = ExecutionModeManager(threshold_seconds=30.0)

    await manager.classify(
        store,
        task_id="task-1",
        run_id="run-1",
        run_status=RunStatus.COMPLETED,
        elapsed_seconds=8.0,
    )
    upgraded = await manager.classify(
        store,
        task_id="task-1",
        run_id="run-2",
        run_status=RunStatus.RUNNING,
        elapsed_seconds=30.0,
    )

    assert upgraded.mode == ExecutionMode.MANAGED
