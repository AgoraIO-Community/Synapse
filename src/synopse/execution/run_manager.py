from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.executor_core import ExecutorEvent, ExecutorEventType
from synopse.protocol import ExecutionRun, ExecutionSession, RunStatus, Task, TaskStatus


class RunManager:
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
        return run

    async def apply_event(
        self,
        store: BlackboardStore,
        task: Task,
        run: ExecutionRun,
        event: ExecutorEvent,
    ) -> None:
        if event.event_type == ExecutorEventType.PROGRESS:
            run.status = RunStatus.RUNNING
            run.latest_progress_message = event.message
            task.status = TaskStatus.RUNNING
        elif event.event_type == ExecutorEventType.BLOCKED:
            run.status = RunStatus.BLOCKED
            run.block_reason = event.message
            task.status = TaskStatus.WAITING_USER_INPUT
        elif event.event_type == ExecutorEventType.COMPLETED:
            run.status = RunStatus.COMPLETED
            run.output_summary = event.message
            task.status = TaskStatus.COMPLETED
        elif event.event_type == ExecutorEventType.FAILED:
            run.status = RunStatus.FAILED
            run.failure_reason = event.message
            task.status = TaskStatus.FAILED
        elif event.event_type == ExecutorEventType.CANCELLED:
            run.status = RunStatus.CANCELLED
            task.status = TaskStatus.CANCELLED

        await store.put_run(run)
        await store.put_task(task)
