import pytest

from synopse.blackboard import InMemoryBlackboard
from synopse.execution import AssignmentManager
from synopse.protocol import Task


@pytest.mark.anyio
async def test_assignment_manager_claims_task():
    store = InMemoryBlackboard()
    manager = AssignmentManager("worker-1")
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Claim me",
        goal="Claim me",
    )
    await store.put_task(task)

    binding = await manager.claim_task(store, task)
    assert binding is not None
    assert binding.claimed_by == "worker-1"
    assert binding.execution_revision == 0
