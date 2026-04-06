from __future__ import annotations

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver, describe_candidates

from .base import ToolInputError


class QueryTaskDetailTool:
    name = "query_task_detail"

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store
        self._resolver = TaskResolver()

    async def __call__(
        self,
        *,
        task_id: str | None = None,
        reference: str | None = None,
    ) -> dict[str, object] | None:
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
            raise ToolInputError("Task not found for detail.", code="task_not_found")
        binding = await self._store.get_binding(task.task_id)
        summary = await self._store.get_summary(task.task_id)
        runs = [run for run in await self._store.list_runs() if run.task_id == task.task_id]
        sessions = [
            session
            for session in await self._store.list_sessions()
            if session.task_id == task.task_id
        ]
        mutations = await self._store.list_mutations(task.task_id)
        return {
            "task": task,
            "binding": binding,
            "summary": summary,
            "runs": runs,
            "sessions": sessions,
            "mutations": mutations,
        }
