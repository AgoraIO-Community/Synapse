from __future__ import annotations

from synopse.blackboard import BlackboardStore, BlackboardQueryService
from synopse.executor_core import ExecutorRegistry

from .assignment import AssignmentManager
from .reconcile import ReconcileLoop
from .run_manager import RunManager
from .session_manager import SessionManager
from .summary_manager import SummaryManager


class ExecutionBrain:
    def __init__(self, store: BlackboardStore, registry: ExecutorRegistry, *, worker_id: str) -> None:
        self._loop = ReconcileLoop(
            store=store,
            queries=BlackboardQueryService(store),
            registry=registry,
            assignment=AssignmentManager(worker_id),
            sessions=SessionManager(),
            runs=RunManager(),
            summaries=SummaryManager(),
        )

    async def tick(self) -> list[str]:
        return await self._loop.tick()
