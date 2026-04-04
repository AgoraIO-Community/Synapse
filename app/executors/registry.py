from __future__ import annotations

from app.executors.base import AsyncExecutor


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, AsyncExecutor] = {}

    def register(self, executor_id: str, executor: AsyncExecutor) -> None:
        self._executors[executor_id] = executor

    def get(self, executor_id: str) -> AsyncExecutor:
        return self._executors[executor_id]

    def list_ids(self) -> list[str]:
        return list(self._executors.keys())
