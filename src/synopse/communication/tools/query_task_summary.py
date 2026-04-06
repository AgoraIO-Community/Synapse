from __future__ import annotations

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver, describe_candidates
from synopse.protocol import TaskSummary

from .base import ToolInputError


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
        resolution = self._resolver.resolve(tasks, task_id=task_id, reference=reference)
        if resolution.status == "ambiguous":
            raise ToolInputError(
                "Task reference is ambiguous. Relevant tasks: "
                f"{describe_candidates(resolution.candidates)}.",
                code="ambiguous_reference",
            )
        task = resolution.task
        if task is None:
            raise ToolInputError("Task not found for summary.", code="task_not_found")
        return await self._store.get_summary(task.task_id)
