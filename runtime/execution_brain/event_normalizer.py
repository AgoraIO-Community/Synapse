from __future__ import annotations

from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.tasks import TaskStatus


def _preferred_task_result_text(event: ExecutionEvent) -> str | None:
    for artifact in event.artifacts_delta:
        inline_value = artifact.inline_value
        if isinstance(inline_value, str) and inline_value.strip():
            return inline_value.strip()
    return event.progress_message


def apply_execution_event_to_task(task, event: ExecutionEvent) -> None:
    task.status = event.status
    if event.event_type == ExecutionEventType.BLOCKED:
        task.block_reason = event.progress_message
    if event.event_type == ExecutionEventType.FAILED:
        task.failure_reason = event.progress_message
    if event.event_type == ExecutionEventType.COMPLETED:
        task.output_summary = _preferred_task_result_text(event)
        task.artifacts.extend(event.artifacts_delta)
        task.block_reason = None
    if event.event_type == ExecutionEventType.CANCELED:
        task.status = TaskStatus.CANCELED
