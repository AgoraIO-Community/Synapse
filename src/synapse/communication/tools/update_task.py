from __future__ import annotations

from uuid import uuid4
from typing import Any

from synapse.blackboard import BlackboardStore
from synapse.communication.resolver import TaskResolver, describe_candidates
from synapse.protocol import MutationType, Task, TaskMutation

from .base import ToolInputError


ALLOWED_PATCH_FIELDS = {
    "goal": str,
    "interruptible": bool,
    "latest_instruction": str,
    "preferred_executor": (str, type(None)),
    "priority": int,
    "requires_confirmation": bool,
    "session_affinity": (str, type(None)),
    "title": str,
}


class UpdateTaskTool:
    name = "update_task"

    def __init__(
        self,
        store: BlackboardStore,
        *,
        valid_executor_types: list[str],
    ) -> None:
        self._store = store
        self._resolver = TaskResolver()
        self._valid_executor_types = list(valid_executor_types)

    async def __call__(
        self,
        *,
        task_id: str | None = None,
        reference: str | None = None,
        patch: dict[str, object],
    ) -> Task:
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
            raise ToolInputError("Task not found for update.", code="task_not_found")
        normalized_patch = self._validate_patch(patch)
        for key, value in normalized_patch.items():
            setattr(task, key, value)
        await self._store.put_task(task)
        await self._store.append_mutation(
            TaskMutation(
                mutation_id=f"mut-{uuid4().hex[:8]}",
                task_id=task.task_id,
                mutation_type=MutationType.UPDATE,
                patch=normalized_patch,
                created_by="communication_brain",
            )
        )
        saved = await self._store.get_task(task.task_id)
        return saved or task

    def _validate_patch(self, patch: dict[str, object]) -> dict[str, object]:
        if not patch:
            raise ToolInputError(
                "update_task patch must include at least one allowed field.",
                code="invalid_patch_shape",
            )

        normalized: dict[str, object] = {}
        invalid_keys = [key for key in patch if key not in ALLOWED_PATCH_FIELDS]
        if invalid_keys:
            allowed = ", ".join(sorted(ALLOWED_PATCH_FIELDS))
            raise ToolInputError(
                f"Invalid update_task fields {invalid_keys}. Allowed fields: {allowed}.",
                code="invalid_patch_shape",
            )

        for key, expected_type in ALLOWED_PATCH_FIELDS.items():
            if key not in patch:
                continue
            value = patch[key]
            if not isinstance(value, expected_type):
                raise ToolInputError(
                    f"Invalid update_task field '{key}'.",
                    code="invalid_patch_shape",
                )
            normalized[key] = value

        preferred_executor = normalized.get("preferred_executor")
        if (
            isinstance(preferred_executor, str)
            and preferred_executor not in self._valid_executor_types
        ):
            allowed = ", ".join(self._valid_executor_types)
            raise ToolInputError(
                f"Invalid update_task preferred_executor '{preferred_executor}'. Use one of: {allowed}.",
                code="invalid_executor_type",
            )
        return normalized
