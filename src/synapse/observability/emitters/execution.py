from __future__ import annotations

from dataclasses import dataclass

from ..logger import DiagnosticLogger


@dataclass(slots=True)
class ExecutionDiagnosticEmitter:
    logger: DiagnosticLogger

    def task_claimed(
        self,
        *,
        task_id: str,
        execution_session_id: str | None,
        worker_id: str,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="exec.task.claimed",
            component="execution.assignment",
            summary="Task claimed for execution",
            task_id=task_id,
            execution_session_id=execution_session_id,
            worker_id=worker_id,
        )

    def task_classified(
        self,
        *,
        task_id: str,
        run_id: str,
        outcome: str,
        reason_code: str,
        elapsed_seconds: float,
        threshold_seconds: float,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="exec.task.classified",
            component="execution.mode_manager",
            summary="Task execution mode classified",
            task_id=task_id,
            run_id=run_id,
            outcome=outcome,
            reason_code=reason_code,
            details={
                "elapsed_seconds": elapsed_seconds,
                "threshold_seconds": threshold_seconds,
            },
        )

    def session_created(
        self,
        *,
        task_id: str,
        execution_session_id: str,
        executor_session_id: str | None,
        executor_type: str,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="exec.session.created",
            component="execution.session_manager",
            summary="Execution session created",
            task_id=task_id,
            execution_session_id=execution_session_id,
            executor_session_id=executor_session_id,
            executor_type=executor_type,
        )

    def session_reused(
        self,
        *,
        task_id: str,
        execution_session_id: str,
        executor_session_id: str | None,
        executor_type: str,
        reason_code: str,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="exec.session.reused",
            component="execution.session_manager",
            summary="Execution session reused",
            task_id=task_id,
            execution_session_id=execution_session_id,
            executor_session_id=executor_session_id,
            executor_type=executor_type,
            reason_code=reason_code,
        )

    def run_started(
        self,
        *,
        task_id: str,
        run_id: str,
        execution_session_id: str,
        executor_type: str,
        claimed_by: str | None,
    ) -> None:
        self.logger.emit_event(
            level="INFO",
            event_name="exec.run.started",
            component="execution.run_manager",
            summary="Execution run started",
            task_id=task_id,
            run_id=run_id,
            execution_session_id=execution_session_id,
            executor_type=executor_type,
            worker_id=claimed_by,
        )

    def run_terminal(
        self,
        *,
        event_name: str,
        task_id: str,
        run_id: str,
        execution_session_id: str,
        executor_type: str,
        summary: str | None,
        reason_code: str | None = None,
    ) -> None:
        level = "ERROR" if event_name == "exec.run.failed" else "INFO"
        self.logger.emit_event(
            level=level,
            event_name=event_name,
            component="execution.run_manager",
            summary="Execution run state updated",
            task_id=task_id,
            run_id=run_id,
            execution_session_id=execution_session_id,
            executor_type=executor_type,
            reason_code=reason_code,
            details={"message": summary} if summary else {},
        )

    def executor_unavailable(
        self,
        *,
        task_id: str,
        executor_type: str,
    ) -> None:
        self.logger.emit_event(
            level="ERROR",
            event_name="exec.executor.unavailable",
            component="execution.reconcile",
            summary="Requested executor is unavailable",
            task_id=task_id,
            executor_type=executor_type,
            reason_code="unknown_executor",
        )
