import pytest

from newbro.blackboard import BlackboardQueryService, InMemoryBlackboard
from newbro.execution import Scheduler
from newbro.protocol import Task, TaskStatus


@pytest.mark.anyio
async def test_scheduler_orders_runnable_tasks_by_priority_then_id():
    store = InMemoryBlackboard()
    query = BlackboardQueryService(store)
    scheduler = Scheduler(query)
    task_a = Task(
        task_id="task_a",
        root_task_id="task_a",
        title="A",
        goal="A",
        status=TaskStatus.QUEUED,
        priority=1,
    )
    task_b = Task(
        task_id="task_b",
        root_task_id="task_b",
        title="B",
        goal="B",
        status=TaskStatus.CREATED,
        priority=10,
    )
    await store.put_task(task_a)
    await store.put_task(task_b)

    ordered = await scheduler.list_runnable_tasks()
    assert [task.task_id for task in ordered] == ["task_b", "task_a"]
