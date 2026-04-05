from __future__ import annotations

from synopse.blackboard import BlackboardStore, BlackboardQueryService
from synopse.executor_core import ExecutorRegistry
from synopse.protocol import Task

from .assignment import AssignmentManager
from .run_manager import RunManager
from .scheduler import Scheduler
from .session_manager import SessionManager
from .summary_manager import SummaryManager


class ReconcileLoop:
    def __init__(
        self,
        store: BlackboardStore,
        queries: BlackboardQueryService,
        registry: ExecutorRegistry,
        assignment: AssignmentManager,
        sessions: SessionManager,
        runs: RunManager,
        summaries: SummaryManager,
    ) -> None:
        self._store = store
        self._queries = queries
        self._registry = registry
        self._assignment = assignment
        self._sessions = sessions
        self._runs = runs
        self._summaries = summaries
        self._scheduler = Scheduler(queries)

    async def tick(self) -> list[str]:
        completed_run_ids: list[str] = []
        tasks = await self._scheduler.list_runnable_tasks()
        for task in tasks:
            claimed = await self._assignment.claim_task(self._store, task)
            if claimed is None:
                continue
            executor_type = task.preferred_executor or "mock"
            executor = self._registry.get(executor_type)
            session, claimed, executor_session = await self._sessions.ensure_session(
                self._store,
                executor,
                task,
                claimed,
            )
            run = await self._runs.create_run(
                self._store,
                task,
                session,
                claimed_by=claimed.claimed_by,
                executor_type=executor_type,
            )
            async for event in executor.run_task(run, task, executor_session):
                await self._runs.apply_event(self._store, task, run, event)
            summary = self._summaries.build_summary(task, run)
            await self._store.put_summary(summary)
            completed_run_ids.append(run.run_id)
        return completed_run_ids
