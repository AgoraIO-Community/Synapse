from __future__ import annotations

from runtime.executors.registry import ExecutorRegistry
from runtime.protocols.tasks import Task


class ExecutorRouter:
    def __init__(self, registry: ExecutorRegistry, default_executor_id: str) -> None:
        self._registry = registry
        self._default_executor_id = default_executor_id

    @property
    def default_executor_id(self) -> str:
        return self._default_executor_id

    def select_executor_id(self, task: Task) -> str:
        if task.assigned_executor:
            return task.assigned_executor
        if task.candidate_executors:
            return task.candidate_executors[0]
        return self._default_executor_id
