from __future__ import annotations

from synopse.communication.context import CommunicationContext
from synopse.protocol import NotificationCandidate


def build_runtime_context(context: CommunicationContext) -> dict[str, object]:
    return {
        "conversation_id": context.conversation_id,
        "active_tasks": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "goal": task.goal,
                "status": task.status,
                "priority": task.priority,
                "latest_instruction": task.latest_instruction,
                "conversational_summary": task.conversational_summary,
                "latest_user_visible_status": task.latest_user_visible_status,
                "note_count": task.note_count,
                "constraint_count": task.constraint_count,
            }
            for task in context.active_tasks
        ],
        "recent_tasks": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "goal": task.goal,
                "status": task.status,
                "priority": task.priority,
                "latest_instruction": task.latest_instruction,
                "conversational_summary": task.conversational_summary,
                "latest_user_visible_status": task.latest_user_visible_status,
                "note_count": task.note_count,
                "constraint_count": task.constraint_count,
            }
            for task in context.recent_tasks
        ],
        "executor_runtime": {
            "has_real_executor": context.executor_runtime.has_real_executor,
            "available_executor_types": context.executor_runtime.available_executor_types,
            "default_executor_type": context.executor_runtime.default_executor_type,
            "executors": context.executor_runtime.executors,
        },
        "available_tools": context.available_tools,
    }


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
