from __future__ import annotations

import time

from synapse.blackboard import BlackboardQueryService, BlackboardStore
from synapse.executor_adapters.acpx import AcpxExecutor, AcpxExecutorSession
from synapse.executor_adapters.codex import CodexExecutor, CodexExecutorSession
from synapse.executor_core import ExecutorRegistry, UnknownExecutorError
from synapse.observability.emitters import ExecutionDiagnosticEmitter
from synapse.protocol import BindingStatus, RunStatus, Task, TaskStatus, TaskSummary

from .assignment import AssignmentManager
from .mode_manager import ExecutionModeManager
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
        modes: ExecutionModeManager,
        summaries: SummaryManager,
        *,
        default_executor_type: str,
        observability: ExecutionDiagnosticEmitter | None = None,
    ) -> None:
        self._store = store
        self._queries = queries
        self._registry = registry
        self._assignment = assignment
        self._sessions = sessions
        self._runs = runs
        self._modes = modes
        self._summaries = summaries
        self._scheduler = Scheduler(queries)
        self._default_executor_type = default_executor_type
        self._observability = observability

    async def tick(self) -> list[str]:
        completed_run_ids: list[str] = []
        tasks = await self._scheduler.list_runnable_tasks()
        for task in tasks:
            claimed = await self._assignment.claim_task(self._store, task)
            if claimed is None:
                continue
            executor_type = task.preferred_executor or self._default_executor_type
            try:
                executor = self._registry.get(executor_type)
            except UnknownExecutorError:
                await self._fail_unknown_executor(task, claimed, executor_type)
                continue
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
            await self._modes.initialize_task_mode(self._store, task.task_id)
            started_at = time.monotonic()
            async for event in executor.run_task(run, task, executor_session):
                await self._runs.apply_event(self._store, task, run, event)
                await self._modes.classify(
                    self._store,
                    task_id=task.task_id,
                    run_id=run.run_id,
                    run_status=run.status,
                    elapsed_seconds=max(0.0, time.monotonic() - started_at),
                )
            await self._sync_executor_session(executor, session, executor_session)
            summary = self._summaries.build_summary(task, run)
            await self._store.put_summary(summary)
            if run.status == RunStatus.COMPLETED:
                completed_run_ids.append(run.run_id)
        return completed_run_ids

    async def _sync_executor_session(
        self,
        executor,
        session,
        executor_session,
    ) -> None:
        if isinstance(executor, AcpxExecutor) and isinstance(executor_session, AcpxExecutorSession):
            session.latest_resume_handle = executor.build_resume_handle(executor_session)
            await self._store.put_session(session)
            return
        if isinstance(executor, CodexExecutor) and isinstance(executor_session, CodexExecutorSession):
            session.latest_resume_handle = executor.build_resume_handle(executor_session)
            await self._store.put_session(session)
            if not executor_session.is_alive():
                self._sessions.drop_live_session(session.execution_session_id)

    async def _fail_unknown_executor(
        self,
        task: Task,
        claimed_binding,
        executor_type: str,
    ) -> None:
        if self._observability is not None:
            self._observability.executor_unavailable(
                task_id=task.task_id,
                executor_type=executor_type,
            )
        task.status = TaskStatus.FAILED
        await self._store.put_task(task)
        await self._store.put_summary(
            TaskSummary(
                task_id=task.task_id,
                operational_summary=f"Unknown executor '{executor_type}'.",
                conversational_summary=f"I couldn't start this task because executor '{executor_type}' is not available.",
                latest_user_visible_status="failed",
                needs_user_input=False,
            )
        )
        await self._store.put_binding(
            claimed_binding.model_copy(
                update={
                    "claimed_by": None,
                    "claim_expires_at": None,
                    "binding_status": BindingStatus.RELEASED,
                }
            )
        )
