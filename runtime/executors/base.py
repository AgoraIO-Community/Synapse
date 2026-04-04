from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from runtime.protocols.execution import ExecutionEvent, ExecutorCapability
from runtime.protocols.tasks import Task


@dataclass(slots=True)
class ExecutionUpdate:
    event: ExecutionEvent
    persist: bool = True
    apply_to_task: bool = True
    emit_conversation: bool = True


def durable_execution_update(event: ExecutionEvent) -> ExecutionUpdate:
    return ExecutionUpdate(event=event)


def transient_execution_update(
    event: ExecutionEvent,
    *,
    apply_to_task: bool = False,
    emit_conversation: bool = False,
) -> ExecutionUpdate:
    return ExecutionUpdate(
        event=event,
        persist=False,
        apply_to_task=apply_to_task,
        emit_conversation=emit_conversation,
    )


ExecutionCallback = Callable[[ExecutionUpdate], Awaitable[None]]


class AsyncExecutor(Protocol):
    async def start_task(
        self, task: Task, callback: ExecutionCallback, *, session_id: str
    ) -> None: ...

    async def update_task(self, task: Task, patch: dict) -> None: ...

    async def cancel_task(self, task_id: str) -> None: ...

    def get_capabilities(self) -> ExecutorCapability: ...
