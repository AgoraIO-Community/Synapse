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
        "When the message updates or controls an existing task, target an existing task reference "
        "instead of creating a new task. When the message is ambiguous, set needs_clarification "
        "and provide a short clarification_reason. "
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
        "You are the Response Generator for a communication brain. "
        "Rewrite the supplied typed conversation action into one short user-facing utterance. "
        "Stay faithful to the action and do not invent state, results, or next steps. "
        "Keep the tone concise and natural."
    )


def build_response_input(action: ConversationAction) -> str:
    return json.dumps(action.model_dump(mode="json"), indent=2, sort_keys=True)
