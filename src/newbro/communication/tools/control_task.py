from __future__ import annotations

from collections.abc import Awaitable, Callable
import inspect
from uuid import uuid4

from newbro.blackboard import BlackboardStore
from newbro.communication.resolver import TaskResolver, describe_candidates
from newbro.protocol import Task, TaskCommand, TaskCommandType

from .base import ToolInputError


class ControlTaskTool:
    name = "control_task"
    allowed_command_types = [command_type.value for command_type in TaskCommandType]

    def __init__(
        self,
        store: BlackboardStore,
        *,
        apply_callback: Callable[[TaskCommand], Awaitable[list[str]] | list[str]] | None = None,
    ) -> None:
        self._store = store
        self._resolver = TaskResolver()
        self._apply_callback = apply_callback

    def set_apply_callback(
        self,
        callback: Callable[[TaskCommand], Awaitable[list[str]] | list[str]] | None,
    ) -> None:
        self._apply_callback = callback

    async def __call__(
        self,
        *,
        command_type: str,
        task_id: str | None = None,
        reference: str | None = None,
        payload: dict[str, object] | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
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
        if self._apply_callback is not None:
            try:
                maybe_awaitable = self._apply_callback(command)
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
            except ValueError as exc:
                raise ToolInputError(str(exc), code="unsupported_command") from exc
        else:
            await self._store.append_command(command)
        return {
            "task": task,
            "command": command,
        }
