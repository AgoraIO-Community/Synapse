from __future__ import annotations

from uuid import uuid4

from synapse.blackboard import BlackboardStore
from synapse.executor_core import ExecutorEvent, ExecutorEventType
from synapse.observability.emitters import ExecutionDiagnosticEmitter
from synapse.protocol import ExecutionRun, ExecutionSession, RunStatus, Task, TaskStatus


class RunManager:
    def __init__(self, *, observability: ExecutionDiagnosticEmitter | None = None) -> None:
        self._observability = observability

    async def create_run(
        self,
        store: BlackboardStore,
        task: Task,
        session: ExecutionSession,
        *,
        claimed_by: str | None,
        executor_type: str,
    ) -> ExecutionRun:
        run = ExecutionRun(
            run_id=f"run-{uuid4().hex[:8]}",
            task_id=task.task_id,
            execution_session_id=session.execution_session_id,
            executor_type=executor_type,
            status=RunStatus.ASSIGNED,
            claimed_by=claimed_by,
            run_revision=task.task_revision,
        )
        session.run_ids.append(run.run_id)
        session.active_run_id = run.run_id
        session.latest_run_id = run.run_id
        await store.put_run(run)
        await store.put_session(session)
        if self._observability is not None:
            self._observability.run_started(
                task_id=task.task_id,
                run_id=run.run_id,
                execution_session_id=session.execution_session_id,
                executor_type=executor_type,
                claimed_by=claimed_by,
            )
        return run

    async def apply_event(
        self,
        store: BlackboardStore,
        task: Task,
        run: ExecutionRun,
        event: ExecutorEvent,
    ) -> None:
        if task.status == TaskStatus.CANCELLED and event.event_type != ExecutorEventType.CANCELLED:
            await store.put_run(run)
            await store.put_task(task)
            return

        if event.event_type == ExecutorEventType.PROGRESS:
            run.status = RunStatus.RUNNING
            run.latest_progress_message = event.message
            task.status = TaskStatus.RUNNING
        elif event.event_type == ExecutorEventType.BLOCKED:
            run.status = RunStatus.BLOCKED
            run.block_reason = event.message
            task.status = TaskStatus.WAITING_USER_INPUT
            if self._observability is not None:
                self._observability.run_terminal(
                    event_name="exec.run.blocked",
                    task_id=task.task_id,
                    run_id=run.run_id,
                    execution_session_id=run.execution_session_id,
                    executor_type=run.executor_type,
                    summary=event.message,
                )
        elif event.event_type == ExecutorEventType.COMPLETED:
            run.status = RunStatus.COMPLETED
            run.output_summary = event.message
            task.status = TaskStatus.COMPLETED
            if self._observability is not None:
                self._observability.run_terminal(
                    event_name="exec.run.completed",
                    task_id=task.task_id,
                    run_id=run.run_id,
                    execution_session_id=run.execution_session_id,
                    executor_type=run.executor_type,
                    summary=event.message,
                )
        elif event.event_type == ExecutorEventType.FAILED:
            run.status = RunStatus.FAILED
            run.failure_reason = event.message
            task.status = TaskStatus.FAILED
            if self._observability is not None:
                self._observability.run_terminal(
                    event_name="exec.run.failed",
                    task_id=task.task_id,
                    run_id=run.run_id,
                    execution_session_id=run.execution_session_id,
                    executor_type=run.executor_type,
                    summary=event.message,
                    reason_code="executor_run_failed",
                )
        elif event.event_type == ExecutorEventType.CANCELLED:
            run.status = RunStatus.CANCELLED
            task.status = TaskStatus.CANCELLED

        await store.put_run(run)
        await store.put_task(task)
