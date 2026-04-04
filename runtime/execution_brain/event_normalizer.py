from __future__ import annotations

from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.tasks import TaskStatus


def apply_execution_event_to_task(task, event: ExecutionEvent) -> None:
    task.status = event.status
    if event.event_type == ExecutionEventType.BLOCKED:
        task.block_reason = event.progress_message
    if event.event_type == ExecutionEventType.FAILED:
        task.failure_reason = event.progress_message
    if event.event_type == ExecutionEventType.COMPLETED:
        task.output_summary = event.progress_message
        task.artifacts.extend(event.artifacts_delta)
        task.block_reason = None
    if event.event_type == ExecutionEventType.CANCELED:
        task.status = TaskStatus.CANCELED
