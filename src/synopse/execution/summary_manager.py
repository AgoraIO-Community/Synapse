from __future__ import annotations

from synopse.protocol import ExecutionRun, RunStatus, Task, TaskSummary


class SummaryManager:
    def build_summary(self, task: Task, run: ExecutionRun) -> TaskSummary:
        if run.status == RunStatus.BLOCKED:
            return TaskSummary(
                task_id=task.task_id,
                operational_summary=run.block_reason,
                conversational_summary=run.block_reason,
                latest_user_visible_status="waiting_user_input",
                needs_user_input=True,
            )
        if run.status == RunStatus.COMPLETED:
            text = run.output_summary or f"Completed: {task.title}"
            return TaskSummary(
                task_id=task.task_id,
                operational_summary=text,
                conversational_summary=text,
                latest_user_visible_status="completed",
                needs_user_input=False,
            )
        if run.status == RunStatus.FAILED:
            text = run.failure_reason or f"Failed: {task.title}"
            return TaskSummary(
                task_id=task.task_id,
                operational_summary=text,
                conversational_summary=text,
                latest_user_visible_status="failed",
                needs_user_input=False,
            )
        text = run.latest_progress_message or f"Running: {task.title}"
        return TaskSummary(
            task_id=task.task_id,
            operational_summary=text,
            conversational_summary=text,
            latest_user_visible_status="running",
            needs_user_input=False,
        )
