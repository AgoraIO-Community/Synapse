from __future__ import annotations

from runtime.executors.base import AsyncExecutor
from runtime.protocols.execution import ExecutorCapability


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, AsyncExecutor] = {}

    def register(self, executor_id: str, executor: AsyncExecutor) -> None:
        self._executors[executor_id] = executor

    def get(self, executor_id: str) -> AsyncExecutor:
        return self._executors[executor_id]

    def list_ids(self) -> list[str]:
        return list(self._executors.keys())

    def list_capabilities(self) -> list[ExecutorCapability]:
        return [executor.get_capabilities() for executor in self._executors.values()]

    def get_capability(self, executor_id: str) -> ExecutorCapability:
        return self.get(executor_id).get_capabilities()
