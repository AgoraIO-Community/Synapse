from __future__ import annotations

from .executor import Executor


class UnknownExecutorError(KeyError):
    pass


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, Executor] = {}

    def register(self, executor: Executor) -> None:
        self._executors[executor.get_capabilities().executor_type] = executor

    def get(self, executor_type: str) -> Executor:
        try:
            return self._executors[executor_type]
        except KeyError as exc:
            raise UnknownExecutorError(f"Unknown executor: {executor_type}") from exc

    def list_executor_types(self) -> list[str]:
        return list(self._executors.keys())
