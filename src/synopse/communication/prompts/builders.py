from __future__ import annotations

import json
from dataclasses import dataclass, field

from synopse.protocol import NotificationCandidate

from ..context import CommunicationContext
from .base.guardrails import GUARDRAILS_PROMPT
from .base.identity import IDENTITY_PROMPT
from .base.reply_style import REPLY_STYLE_PROMPT
from .base.tool_policy import build_tool_policy_prompt
from .examples.notification_style import NOTIFICATION_STYLE_EXAMPLES_PROMPT
from .examples.tool_usage import build_tool_usage_examples_prompt
from .runtime_context import (
    build_notification_candidates_payload,
    build_notification_rendering_context,
    build_runtime_context,
)
from .tasks.normal_reply import build_normal_reply_task_prompt
from .tasks.proactive_notification import PROACTIVE_NOTIFICATION_PROMPT


@dataclass(slots=True)
class PromptBuildResult:
    messages: list[dict[str, object]] = field(default_factory=list)
    prompt_sections: list[str] = field(default_factory=list)
    notification_key_task_id: str | None = None
    notification_relevant_task_ids: list[str] = field(default_factory=list)
    notification_recent_chat_turn_count: int = 0


REPLY_PROMPT_SECTIONS = [
    "identity",
    "tool_policy",
    "reply_style",
    "guardrails",
    "normal_reply",
    "tool_usage_examples",
    "runtime_context",
]

NOTIFICATION_PROMPT_SECTIONS = [
    "identity",
    "reply_style",
    "guardrails",
    "proactive_notification",
    "notification_style_examples",
    "notification_rendering_context",
    "notification_candidates",
]


def build_reply_messages(
    *,
    user_text: str,
    context: CommunicationContext,
) -> list[dict[str, object]]:
    return build_reply_prompt_request(user_text=user_text, context=context).messages


def build_reply_prompt_request(
    *,
    user_text: str,
    context: CommunicationContext,
) -> PromptBuildResult:
    return PromptBuildResult(
        messages=[
        _message("system", IDENTITY_PROMPT),
        _message("system", build_tool_policy_prompt(context)),
        _message("system", REPLY_STYLE_PROMPT),
        _message("system", GUARDRAILS_PROMPT),
        _message(
            "system",
            build_normal_reply_task_prompt(
                user_text=user_text,
                available_tools=context.available_tools,
            ),
        ),
        _message("system", build_tool_usage_examples_prompt(context)),
        _message("system", json.dumps(build_runtime_context(context))),
        *[_message(entry.role, entry.text) for entry in context.recent_history],
        ],
        prompt_sections=list(REPLY_PROMPT_SECTIONS),
    )


def build_notification_messages(
    *,
    context: CommunicationContext,
    candidates: list[NotificationCandidate],
) -> list[dict[str, object]]:
    return build_notification_prompt_request(context=context, candidates=candidates).messages


def build_notification_prompt_request(
    *,
    context: CommunicationContext,
    candidates: list[NotificationCandidate],
) -> PromptBuildResult:
    rendering_context = build_notification_rendering_context(context, candidates)
    key_task = rendering_context.get("key_task")
    relevant_tasks = rendering_context.get("relevant_tasks", [])
    recent_chat_history = rendering_context.get("recent_chat_history", [])
    return PromptBuildResult(
        messages=[
        _message("system", IDENTITY_PROMPT),
        _message("system", REPLY_STYLE_PROMPT),
        _message("system", GUARDRAILS_PROMPT),
        _message("system", PROACTIVE_NOTIFICATION_PROMPT),
        _message("system", NOTIFICATION_STYLE_EXAMPLES_PROMPT),
        _message("system", json.dumps(rendering_context)),
        _message("system", json.dumps(build_notification_candidates_payload(candidates))),
        ],
        prompt_sections=list(NOTIFICATION_PROMPT_SECTIONS),
        notification_key_task_id=(
            str(key_task.get("task_id")) if isinstance(key_task, dict) and key_task.get("task_id") else None
        ),
        notification_relevant_task_ids=[
            str(task.get("task_id"))
            for task in relevant_tasks
            if isinstance(task, dict) and task.get("task_id")
        ],
        notification_recent_chat_turn_count=len(recent_chat_history) if isinstance(recent_chat_history, list) else 0,
    )


def _message(role: str, text: str) -> dict[str, object]:
    return {"role": role, "content": text}
