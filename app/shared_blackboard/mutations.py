from __future__ import annotations

from app.infrastructure.time import utc_now
from app.protocols.runtime import ContextPatch, PatchScope
from app.protocols.tasks import ControlCommandType, Task, TaskStatus
from app.shared_blackboard.models import SessionState


def apply_context_patch(session: SessionState, patch: ContextPatch) -> None:
    target: dict
    if patch.scope == PatchScope.CONVERSATION:
        target = session.conversation_state
    elif patch.scope == PatchScope.STRATEGY:
        target = session.strategy_state
    elif patch.scope == PatchScope.TASK and patch.applies_to_task_id:
        task = session.task_registry[patch.applies_to_task_id]
        task.input_context.update(patch.patch)
        task.updated_at = utc_now()
        return
    else:
        target = session.conversation_state

    target.update(patch.patch)


def upsert_task(session: SessionState, task: Task) -> Task:
    task.updated_at = utc_now()
    session.task_registry[task.task_id] = task
    return task


def apply_task_update(task: Task, patch: dict) -> Task:
    for key, value in patch.items():
        if hasattr(task, key):
            setattr(task, key, value)
        else:
            task.input_context[key] = value
    task.latest_instruction = patch.get("latest_instruction", task.latest_instruction)
    task.updated_at = utc_now()
    return task


def apply_control(task: Task, command_type: ControlCommandType) -> Task:
    if command_type == ControlCommandType.PAUSE_TASK and task.status == TaskStatus.RUNNING:
        task.status = TaskStatus.PAUSED
    elif command_type == ControlCommandType.RESUME_TASK and task.status in {
        TaskStatus.PAUSED,
        TaskStatus.BLOCKED,
    }:
        task.status = TaskStatus.RUNNING
    elif command_type == ControlCommandType.CANCEL_TASK:
        task.status = TaskStatus.CANCELED
    elif command_type == ControlCommandType.RETRY_TASK and task.status in {
        TaskStatus.FAILED,
        TaskStatus.BLOCKED,
        TaskStatus.CANCELED,
    }:
        task.status = TaskStatus.QUEUED
        task.failure_reason = None
        task.block_reason = None
    task.updated_at = utc_now()
    return task
