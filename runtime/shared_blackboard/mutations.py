from __future__ import annotations

from datetime import datetime

from runtime.infrastructure.time import utc_now
from runtime.protocols.runtime import ContextPatch, PatchScope
from runtime.protocols.tasks import ControlCommandType, Task, TaskStatus
from runtime.shared_blackboard.blackboard_state import BlackboardSessionState

MESSAGE_HISTORY_KEY = "message_history"
MAX_MESSAGE_HISTORY = 30


def _serialize_message_timestamp(timestamp) -> str:
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    if timestamp is None:
        return utc_now().isoformat()
    return str(timestamp)


def _serialize_message_history_entry(item: dict) -> dict:
    serialized = dict(item)
    serialized["timestamp"] = _serialize_message_timestamp(item.get("timestamp"))
    return serialized


def append_message_history(
    session: BlackboardSessionState,
    *,
    role: str,
    text: str,
    message_id: str,
    task_id: str | None = None,
    timestamp=None,
) -> None:
    history = session.conversation_state.setdefault(MESSAGE_HISTORY_KEY, [])
    history.append(
        _serialize_message_history_entry(
            {
            "role": role,
            "text": text,
            "message_id": message_id,
            "task_id": task_id,
            "timestamp": timestamp or utc_now(),
            }
        )
    )
    session.conversation_state[MESSAGE_HISTORY_KEY] = history[-MAX_MESSAGE_HISTORY:]


def get_message_history(
    session: BlackboardSessionState,
    *,
    limit: int = MAX_MESSAGE_HISTORY,
) -> list[dict]:
    history = session.conversation_state.get(MESSAGE_HISTORY_KEY, [])
    return [_serialize_message_history_entry(item) for item in history[-limit:]]


def associate_message_history_task(
    session: BlackboardSessionState,
    *,
    message_id: str,
    task_id: str,
) -> None:
    history = session.conversation_state.get(MESSAGE_HISTORY_KEY, [])
    for item in history:
        if item.get("message_id") == message_id:
            item["task_id"] = task_id


def find_message_history_entry(
    session: BlackboardSessionState,
    *,
    message_id: str | None,
) -> dict | None:
    if message_id is None:
        return None
    history = session.conversation_state.get(MESSAGE_HISTORY_KEY, [])
    for item in history:
        if item.get("message_id") == message_id:
            return _serialize_message_history_entry(item)
    return None


def get_task_message_history(
    session: BlackboardSessionState,
    *,
    task_id: str,
    limit: int = MAX_MESSAGE_HISTORY,
) -> list[dict]:
    history = session.conversation_state.get(MESSAGE_HISTORY_KEY, [])
    task_history = [
        _serialize_message_history_entry(item)
        for item in history
        if item.get("task_id") == task_id
    ]
    return task_history[-limit:]


def apply_context_patch(session: BlackboardSessionState, patch: ContextPatch) -> None:
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


def upsert_task(session: BlackboardSessionState, task: Task) -> Task:
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
    if command_type == ControlCommandType.CANCEL_TASK:
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
