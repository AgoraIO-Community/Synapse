from __future__ import annotations

import json

from runtime.protocols.conversation import ConversationAction
from runtime.protocols.stream import SessionSnapshot


def build_interpreter_instructions() -> str:
    return (
        "You are the Message Interpreter for a communication-brain/execution-brain runtime. "
        "Interpret the latest user message into a strictly structured routing_decision and "
        "action_bundle. Do not produce prose. Preserve the supplied message_id in both objects. "
        "Generate id strings with prefixes like decision_, bundle_, and action_. "
        "Use only the flat action fields defined by the schema. "
        "The communication brain does not have external lookup or system-state capabilities. "
        "Use conversation_only only for social chat, small talk, thanks, and meta questions about Synopse itself. "
        "If the user is asking for information that would require checking the world, the system, files, tools, or any executor capability, route it as task. "
        "Set conversation_mode to 'task' for actionable requests and capability-gated questions. "
        "Set conversation_mode to 'clarification' only when you truly cannot act safely on a task or control request. "
        "When the message updates or controls an existing task, target an existing task reference "
        "instead of creating a new task. When the message is ambiguous, set needs_clarification "
        "and provide a short clarification_reason. "
        "Examples: 'hi' -> conversation_only, 'how are you' -> conversation_only, "
        "'what does this system do?' -> conversation_only, "
        "'what time is it?' -> task with create_task, "
        "'search flights to Tokyo tomorrow' -> task with create_task, "
        "'continue with the recipient info' -> update_task, "
        "'resume the paused task' -> control_task resume_task, "
        "'pause it' with no active task -> clarification. "
        "For fields that do not apply to a given action type, leave strings empty and booleans false. "
        "Do not add any keys that are not in the schema."
    )


def build_interpreter_input(*, message_id: str, text: str, snapshot: SessionSnapshot) -> str:
    payload = {
        "message_id": message_id,
        "latest_user_message": text,
        "session_snapshot": snapshot.model_dump(mode="json"),
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
        "response_context": action.metadata,
    }
    return json.dumps(payload, indent=2, sort_keys=True)
