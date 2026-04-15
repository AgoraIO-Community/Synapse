import pytest

from synapse.executor_adapters.mock import MockExecutor
from synapse.protocol import ExecutionRun, Task


@pytest.mark.anyio
async def test_mock_executor_emits_completed_event():
    executor = MockExecutor()
    session = await executor.create_session()
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Draft email",
        goal="Draft email",
    )
    run = ExecutionRun(
        run_id="run_1",
        task_id="task_1",
        execution_session_id="exec_1",
        executor_type="mock",
    )

    events = [event async for event in executor.run_task(run, task, session)]
    assert events[-1].event_type.value == "completed"


@pytest.mark.anyio
async def test_mock_executor_emits_blocked_event():
    executor = MockExecutor()
    session = await executor.create_session()
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Need input",
        goal="Need input",
        metadata={"mock_behavior": "blocked"},
    )
    run = ExecutionRun(
        run_id="run_1",
        task_id="task_1",
        execution_session_id="exec_1",
        executor_type="mock",
    )

    events = [event async for event in executor.run_task(run, task, session)]
    assert events[-1].event_type.value == "blocked"
