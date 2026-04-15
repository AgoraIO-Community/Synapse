from __future__ import annotations

from synapse.blackboard import BlackboardQueryService, BlackboardStore
from synapse.executor_core import ExecutorRegistry
from synapse.observability.emitters.execution import ExecutionDiagnosticEmitter

from .assignment import AssignmentManager
from .mode_manager import ExecutionModeManager
from .reconcile import ReconcileLoop
from .run_manager import RunManager
from .session_manager import SessionManager
from .summary_manager import SummaryManager


class ExecutionBrain:
    def __init__(
        self,
        store: BlackboardStore,
        registry: ExecutorRegistry,
        *,
        worker_id: str,
        default_executor_type: str,
        observability: ExecutionDiagnosticEmitter | None = None,
    ) -> None:
        self._loop = ReconcileLoop(
            store=store,
            queries=BlackboardQueryService(store),
            registry=registry,
            assignment=AssignmentManager(worker_id, observability=observability),
            sessions=SessionManager(observability=observability),
            runs=RunManager(observability=observability),
            modes=ExecutionModeManager(observability=observability),
            summaries=SummaryManager(),
            default_executor_type=default_executor_type,
            observability=observability,
        )

    async def tick(self) -> list[str]:
        return await self._loop.tick()
