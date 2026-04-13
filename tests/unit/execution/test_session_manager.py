import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.execution import SessionManager
from synapse.executor_adapters.mock import MockExecutor
from synapse.protocol import SessionBinding, Task


@pytest.mark.anyio
async def test_session_manager_creates_and_reuses_session():
    store = InMemoryBlackboard()
    manager = SessionManager()
    executor = MockExecutor()
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Reuse session",
        goal="Reuse session",
    )
    binding = SessionBinding(task_id="task_1", claimed_by="worker-1")

    session_one, binding_one, executor_session_one = await manager.ensure_session(
        store, executor, task, binding
    )
    session_two, binding_two, executor_session_two = await manager.ensure_session(
        store, executor, task, binding_one
    )

    assert session_one.execution_session_id == session_two.execution_session_id
    assert binding_two.session_id == binding_one.session_id
    assert executor_session_one.session_id == executor_session_two.session_id
