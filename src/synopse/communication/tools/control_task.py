from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver
from synopse.protocol import Task, TaskCommand, TaskCommandType

from .base import ToolInputError


class ControlTaskTool:
    name = "control_task"
    allowed_command_types = [command_type.value for command_type in TaskCommandType]

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store
        self._resolver = TaskResolver()

    async def __call__(
        self,
        *,
        command_type: str,
        task_id: str | None = None,
        reference: str | None = None,
        payload: dict[str, object] | None = None,
        reason: str | None = None,
    ) -> TaskCommand:
        tasks = await self._store.list_tasks()
        task = self._resolver.resolve(tasks, task_id=task_id, reference=reference)
        if task is None:
            raise ToolInputError("Task not found for control.", code="task_not_found")
        try:
            normalized_command_type = TaskCommandType(command_type)
        except ValueError as exc:
            allowed = ", ".join(self.allowed_command_types)
            raise ToolInputError(
                f"Invalid control_task command_type '{command_type}'. Use one of: {allowed}.",
                code="invalid_command_type",
            ) from exc
        command = TaskCommand(
            command_id=f"cmd-{uuid4().hex[:8]}",
            task_id=task.task_id,
            command_type=normalized_command_type,
            payload=payload or {},
            created_by="communication_brain",
            reason=reason,
        )
        await self._store.append_command(command)
        return command
