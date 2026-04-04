from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from runtime.protocols.execution import ExecutionEvent, ExecutorCapability
from runtime.protocols.tasks import Task


ExecutionCallback = Callable[[ExecutionEvent], Awaitable[None]]


class AsyncExecutor(Protocol):
    async def start_task(
        self, task: Task, callback: ExecutionCallback, *, session_id: str
    ) -> None: ...

    async def update_task(self, task: Task, patch: dict) -> None: ...

    async def cancel_task(self, task_id: str) -> None: ...

    def get_capabilities(self) -> ExecutorCapability: ...
