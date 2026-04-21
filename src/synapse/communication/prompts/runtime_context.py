from __future__ import annotations

from datetime import datetime

from synapse.communication.context import CommunicationContext
from synapse.protocol import NotificationCandidate, Task, TaskExecutionDetailEntry, TaskSummary


NOTIFICATION_CHAT_HISTORY_LIMIT = 6


def build_runtime_context(context: CommunicationContext) -> dict[str, object]:
    result: dict[str, object] = {
        "conversation_id": context.conversation_id,
        "focused_task_ids": context.focused_task_ids,
        "focused_tasks": [_task_brief_payload(task) for task in context.focused_tasks],
        "active_tasks": [_task_brief_payload(task) for task in context.active_tasks],
        "recent_tasks": [_task_brief_payload(task) for task in context.recent_tasks],
        "task_execution_details": {
            task_id: [_execution_detail_payload(entry) for entry in entries]
            for task_id, entries in context.task_execution_details.items()
        },
        "executor_runtime": {
            "has_real_executor": context.executor_runtime.has_real_executor,
            "available_executor_types": context.executor_runtime.available_executor_types,
            "default_executor_type": context.executor_runtime.default_executor_type,
            "executors": context.executor_runtime.executors,
        },
        "available_tools": context.available_tools,
    }
    if context.personas:
        result["personas"] = context.personas
    if context.interaction_requests:
        result["interaction_requests"] = context.interaction_requests
    return result


def build_notification_candidates_payload(
    candidates: list[NotificationCandidate],
) -> dict[str, object]:
    return {
        "notification_candidates": [
            {
                "candidate_type": candidate.candidate_type.value,
                "task_id": candidate.task_id,
                "summary_short": candidate.summary_short,
                "priority": candidate.priority.value,
            }
            for candidate in candidates
        ]
    }


def build_notification_rendering_context(
    context: CommunicationContext,
    candidates: list[NotificationCandidate],
) -> dict[str, object]:
    recent_chat_history = [
        {"role": entry.role, "text": entry.text}
        for entry in context.recent_history[-NOTIFICATION_CHAT_HISTORY_LIMIT:]
    ]
    key_candidate = _select_key_candidate(candidates)
    candidate_by_task = _latest_candidate_by_task(candidates)
    ordered_task_ids: list[str] = []
    if key_candidate is not None:
        ordered_task_ids.append(key_candidate.task_id)
    remaining_task_ids = [
        task_id
        for task_id, _candidate in sorted(
            candidate_by_task.items(),
            key=lambda item: _candidate_sort_key(item[1]),
            reverse=True,
        )
        if task_id not in ordered_task_ids
    ]
    ordered_task_ids.extend(remaining_task_ids)

    relevant_tasks = [
        _notification_task_payload(
            task_id=task_id,
            task=_task_by_id(context, task_id),
            summary=context.summaries.get(task_id),
            candidate=candidate_by_task[task_id],
        )
        for task_id in ordered_task_ids
    ]
    key_task = relevant_tasks[0] if relevant_tasks else None
    return {
        "recent_chat_history": recent_chat_history,
        "key_task": key_task,
        "relevant_tasks": relevant_tasks,
    }


def _task_brief_payload(task: object) -> dict[str, object]:
    return {
        "task_id": getattr(task, "task_id", None),
        "title": getattr(task, "title", None),
        "goal": getattr(task, "goal", None),
        "status": getattr(task, "status", None),
        "priority": getattr(task, "priority", None),
        "latest_instruction": getattr(task, "latest_instruction", None),
        "conversational_summary": getattr(task, "conversational_summary", None),
        "latest_user_visible_status": getattr(task, "latest_user_visible_status", None),
        "note_count": getattr(task, "note_count", None),
        "constraint_count": getattr(task, "constraint_count", None),
        "persona_name": getattr(task, "persona_name", None),
        "persona_avatar": getattr(task, "persona_avatar", None),
    }


def _execution_detail_payload(entry: TaskExecutionDetailEntry) -> dict[str, object]:
    return {
        "run_id": entry.run_id,
        "execution_session_id": entry.execution_session_id,
        "event_type": entry.event_type,
        "text": entry.text,
        "created_at": entry.created_at,
    }


def _notification_task_payload(
    *,
    task_id: str,
    task: Task | None,
    summary: TaskSummary | None,
    candidate: NotificationCandidate,
) -> dict[str, object]:
    if task is None:
        return {
            "task_id": task_id,
            "title": None,
            "goal": None,
            "status": None,
            "priority": None,
            "latest_instruction": None,
            "conversational_summary": candidate.summary_short,
            "latest_user_visible_status": None,
            "note_count": None,
            "constraint_count": None,
        }
    notes = task.metadata.get("notes", [])
    constraints = task.metadata.get("constraints", [])
    return {
        "task_id": task.task_id,
        "title": task.title,
        "goal": task.goal,
        "status": task.status.value,
        "priority": task.priority,
        "latest_instruction": task.latest_instruction,
        "conversational_summary": summary.conversational_summary if summary is not None else None,
        "latest_user_visible_status": (
            summary.latest_user_visible_status if summary is not None else None
        ),
        "note_count": len(notes) if isinstance(notes, list) else 0,
        "constraint_count": len(constraints) if isinstance(constraints, list) else 0,
    }


def _task_by_id(context: CommunicationContext, task_id: str) -> Task | None:
    for task in context.tasks:
        if task.task_id == task_id:
            return task
    return None


def _select_key_candidate(
    candidates: list[NotificationCandidate],
) -> NotificationCandidate | None:
    if not candidates:
        return None
    return max(
        enumerate(candidates),
        key=lambda item: (_candidate_sort_key(item[1]), item[0]),
    )[1]


def _latest_candidate_by_task(
    candidates: list[NotificationCandidate],
) -> dict[str, NotificationCandidate]:
    latest: dict[str, NotificationCandidate] = {}
    indexes: dict[str, int] = {}
    for index, candidate in enumerate(candidates):
        existing = latest.get(candidate.task_id)
        if existing is None:
            latest[candidate.task_id] = candidate
            indexes[candidate.task_id] = index
            continue
        if (_candidate_sort_key(candidate), index) >= (
            _candidate_sort_key(existing),
            indexes[candidate.task_id],
        ):
            latest[candidate.task_id] = candidate
            indexes[candidate.task_id] = index
    return latest


def _candidate_sort_key(candidate: NotificationCandidate) -> datetime:
    return datetime.fromisoformat(candidate.created_at)
