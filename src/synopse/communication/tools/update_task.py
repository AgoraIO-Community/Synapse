from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver
from synopse.protocol import MutationType, Task, TaskMutation

from .base import ToolInputError


class UpdateTaskTool:
    name = "update_task"

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store
        self._resolver = TaskResolver()

    async def __call__(
        self,
        *,
        task_id: str | None = None,
        reference: str | None = None,
        patch: dict[str, object],
    ) -> Task:
        tasks = await self._store.list_tasks()
        task = self._resolver.resolve(tasks, task_id=task_id, reference=reference)
        if task is None:
            raise ToolInputError("Task not found for update.", code="task_not_found")
        for key, value in patch.items():
            if hasattr(task, key):
                setattr(task, key, value)
            else:
                task.metadata[key] = value
        if "latest_instruction" in patch and isinstance(patch["latest_instruction"], str):
            task.latest_instruction = patch["latest_instruction"]
        await self._store.put_task(task)
        await self._store.append_mutation(
            TaskMutation(
                mutation_id=f"mut-{uuid4().hex[:8]}",
                task_id=task.task_id,
                mutation_type=MutationType.UPDATE,
                patch=patch,
                created_by="communication_brain",
            )
        )
        saved = await self._store.get_task(task.task_id)
        return saved or task
