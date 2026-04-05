from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver
from synopse.protocol import Task, TaskCommand, TaskCommandType


class ControlTaskTool:
    name = "control_task"

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
            raise KeyError("Task not found for control.")
        command = TaskCommand(
            command_id=f"cmd-{uuid4().hex[:8]}",
            task_id=task.task_id,
            command_type=TaskCommandType(command_type),
            payload=payload or {},
            created_by="communication_brain",
            reason=reason,
        )
        await self._store.append_command(command)
        return command
