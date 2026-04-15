from __future__ import annotations

from synapse.blackboard import BlackboardQueryService
from synapse.protocol import Task


class Scheduler:
    def __init__(self, queries: BlackboardQueryService) -> None:
        self._queries = queries

    async def list_runnable_tasks(self) -> list[Task]:
        tasks = await self._queries.list_runnable_tasks()
        return sorted(tasks, key=lambda task: (-task.priority, task.task_id))
