from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver, describe_candidates
from synopse.protocol import MutationType, Task, TaskMutation

from .base import ToolInputError


class AddTaskNoteTool:
    name = "add_task_note"

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store
        self._resolver = TaskResolver()

    async def __call__(
        self,
        *,
        note: str,
        task_id: str | None = None,
        reference: str | None = None,
    ) -> Task:
        task = await self._resolve_task(task_id=task_id, reference=reference)
        notes = list(task.metadata.get("notes", []))
        notes.append(note)
        task.metadata["notes"] = notes
        await self._store.put_task(task)
        await self._store.append_mutation(
            TaskMutation(
                mutation_id=f"mut-{uuid4().hex[:8]}",
                task_id=task.task_id,
                mutation_type=MutationType.ADD_TASK_NOTE,
                patch={"note": note},
                created_by="communication_brain",
            )
        )
        saved = await self._store.get_task(task.task_id)
        return saved or task

    async def _resolve_task(
        self,
        *,
        task_id: str | None,
        reference: str | None,
    ) -> Task:
        tasks = await self._store.list_tasks()
        resolution = self._resolver.resolve(tasks, task_id=task_id, reference=reference)
        if resolution.status == "resolved" and resolution.task is not None:
            return resolution.task
        if resolution.status == "ambiguous":
            raise ToolInputError(
                "Task reference is ambiguous. Relevant tasks: "
                f"{describe_candidates(resolution.candidates)}.",
                code="ambiguous_reference",
            )
        raise ToolInputError("Task not found for note.", code="task_not_found")
