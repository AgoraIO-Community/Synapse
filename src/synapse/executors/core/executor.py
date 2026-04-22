from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from synapse.protocol import ExecutionRun, Task

from .capabilities import ExecutorCapabilities
from .events import ExecutorEvent
from .session import ExecutorSession


class Executor(Protocol):
    def get_capabilities(self) -> ExecutorCapabilities:
        ...

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        ...

    def run_task(
        self,
        run: ExecutionRun,
        task: Task,
        session: ExecutorSession,
    ) -> AsyncIterator[ExecutorEvent]:
        ...

    async def cancel_run(self, run_id: str) -> None:
        ...

    async def pause_run(self, run_id: str) -> None:
        ...
