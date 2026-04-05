from __future__ import annotations

import json
from typing import Any

from runtime.protocols.conversation import ConversationAction
from runtime.protocols.stream import SessionSnapshot
from runtime.protocols.tasks import TaskStatus


INTERPRETER_MESSAGE_HISTORY_LIMIT = 10
INTERPRETER_PROMPT_CACHE_KEY = "synopse:message-interpreter:v4"


def build_interpreter_instructions() -> str:
    return (
        "You are the Message Interpreter for Synopse. "
        "Return only schema-valid structured output. Preserve message_id and generate ids with "
        "decision_, bundle_, and action_ prefixes. "
        "Use only fields relevant to the chosen action type. "
        "conversation_only is for social chat, thanks, persona or subjective questions, and "
        "meta questions about Synopse itself. "
        "task is for actionable requests or anything requiring executor, world, system, file, "
        "or tool access. "
        "clarification is only for task or control intent that cannot be acted on safely. "
        "Use message_history, pending_clarifications, active_tasks, and executor_capabilities as context. "
        "When a follow-up likely refers to an active task, prefer update_task or control_task over creating a new task. "
        "For create_task and update_task, always provide a concrete non-empty goal; title may be omitted if redundant. "
        "Prefer update_task or control_task over create_task when the message refers to an "
        "existing task. "
        "Examples: 'hi' -> conversation_only; 'how do you feel?' -> conversation_only; "
        "'what time is it?' -> create_task; 'what is today's weather?' -> create_task; "
        "'check the logs' -> create_task; 'continue with the recipient info' -> update_task; "
        "'pause it' with no active task -> clarification. "
        "Do not add any keys that are not in the schema."
    )


def _message_history_context(snapshot: SessionSnapshot) -> list[dict[str, Any]]:
    history = snapshot.conversation_state.get("message_history", [])
    return history[-INTERPRETER_MESSAGE_HISTORY_LIMIT:]


def _pending_clarification_context(snapshot: SessionSnapshot) -> list[dict[str, Any]]:
    return [
        {
            "action_type": action.action_type.value,
            "target_task_id": action.target_task_id,
            "reason": action.reason,
        }
        for action in snapshot.pending_clarifications
    ]


def _executor_capability_context(snapshot: SessionSnapshot) -> list[dict[str, Any]]:
    return [
        {
            "executor_id": capability.executor_id,
            "capability_tags": capability.capability_tags,
            "supports_cancel": capability.supports_cancel,
            "supports_streaming": capability.supports_streaming,
        }
        for capability in snapshot.executor_capabilities
    ]


def _active_task_context(snapshot: SessionSnapshot) -> list[dict[str, str]]:
    return [
        {
            "task_id": task.task_id,
            "goal": task.goal,
        }
        for task in snapshot.task_registry
        if task.status in {
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
            TaskStatus.BLOCKED,
        }
    ]


def build_interpreter_input(*, message_id: str, text: str, snapshot: SessionSnapshot) -> str:
    payload = {
        "message_id": message_id,
        "latest_user_message": text,
        "message_history": _message_history_context(snapshot),
        "pending_clarifications": _pending_clarification_context(snapshot),
        "active_tasks": _active_task_context(snapshot),
        "executor_capabilities": _executor_capability_context(snapshot),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def build_response_instructions() -> str:
    return (
        "You are the Response Generator for Synopse. "
        "Produce the next thing the agent should say to the human based on the supplied typed action and all context provided with it. "
        "Do not mechanically restate the user's words. Reply from the agent's perspective. "
        "Use metadata as operational context, including the latest user message, planned actions, execution results, and artifacts. "
        "For chat_reply, answer the human directly using the provided context. "
        "For acknowledge, briefly confirm the work you are about to do. "
        "For inform_done, inform_failed, inform_blocked, and inform_progress, present the execution outcome naturally to the human. "
        "Prefer one or two short sentences that sound natural when spoken aloud. "
        "Summarize the full task result instead of reading raw output verbatim unless the result is already brief and conversational. "
        "Keep the user-facing reply concise and narrative, while fuller task output can live elsewhere. "
        "Stay faithful to the provided context and do not invent unsupported facts or results. "
        "Keep the tone concise and natural."
    )


def build_response_input(action: ConversationAction) -> str:
    payload = {
        "action_type": action.action_type.value,
        "target_task_id": action.target_task_id,
        "urgency": action.urgency.value,
        "reason": action.reason,
        "render_text": action.render_text,
        "user_message": action.metadata.get("user_message"),
        "message_history": action.metadata.get("message_history", []),
        "response_context": action.metadata,
    }
    return json.dumps(payload, indent=2, sort_keys=True)
