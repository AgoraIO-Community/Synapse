from __future__ import annotations

from synopse.blackboard import BlackboardStore
from synopse.protocol import ExecutionMode, RunStatus, TaskExecutionMode


TERMINAL_RUN_STATUSES = {
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
}


class ExecutionModeManager:
    def __init__(self, *, threshold_seconds: float = 30.0) -> None:
        self._threshold_seconds = threshold_seconds

    async def initialize_task_mode(self, store: BlackboardStore, task_id: str) -> TaskExecutionMode:
        existing = await store.get_execution_mode(task_id)
        if existing is not None:
            return existing
        execution_mode = TaskExecutionMode(task_id=task_id, mode=ExecutionMode.UNDECIDED)
        await store.put_execution_mode(execution_mode)
        return execution_mode

    async def classify(
        self,
        store: BlackboardStore,
        *,
        task_id: str,
        run_id: str,
        run_status: RunStatus,
        elapsed_seconds: float,
    ) -> TaskExecutionMode:
        current = await self.initialize_task_mode(store, task_id)
        next_mode = self._next_mode(current.mode, run_status=run_status, elapsed_seconds=elapsed_seconds)
        updated = current.model_copy(
            update={
                "mode": next_mode,
                "decided_from_run_id": run_id if next_mode != ExecutionMode.UNDECIDED else current.decided_from_run_id,
                "elapsed_seconds": elapsed_seconds,
            }
        )
        if updated != current:
            await store.put_execution_mode(updated)
        return updated

    def _next_mode(
        self,
        current_mode: ExecutionMode,
        *,
        run_status: RunStatus,
        elapsed_seconds: float,
    ) -> ExecutionMode:
        if current_mode == ExecutionMode.MANAGED:
            return ExecutionMode.MANAGED
        if elapsed_seconds >= self._threshold_seconds:
            return ExecutionMode.MANAGED
        if current_mode == ExecutionMode.LIGHTWEIGHT:
            return ExecutionMode.LIGHTWEIGHT
        if run_status in TERMINAL_RUN_STATUSES:
            return ExecutionMode.LIGHTWEIGHT
        return ExecutionMode.UNDECIDED
