from __future__ import annotations

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver
from synopse.protocol import TaskSummary


class QueryTaskSummaryTool:
    name = "query_task_summary"

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store
        self._resolver = TaskResolver()

    async def __call__(
        self,
        *,
        task_id: str | None = None,
        reference: str | None = None,
    ) -> TaskSummary | None:
        tasks = await self._store.list_tasks()
        task = self._resolver.resolve(tasks, task_id=task_id, reference=reference)
        if task is None:
            return None
        return await self._store.get_summary(task.task_id)
