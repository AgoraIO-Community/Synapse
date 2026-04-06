from __future__ import annotations

import json

from synopse.protocol import NotificationCandidate

from ..context import CommunicationContext
from .base.guardrails import GUARDRAILS_PROMPT
from .base.identity import IDENTITY_PROMPT
from .base.reply_style import REPLY_STYLE_PROMPT
from .base.tool_policy import build_tool_policy_prompt
from .examples.notification_style import NOTIFICATION_STYLE_EXAMPLES_PROMPT
from .examples.tool_usage import build_tool_usage_examples_prompt
from .runtime_context import build_notification_candidates_payload, build_runtime_context
from .tasks.normal_reply import build_normal_reply_task_prompt
from .tasks.proactive_notification import PROACTIVE_NOTIFICATION_PROMPT


def build_reply_messages(
    *,
    user_text: str,
    context: CommunicationContext,
) -> list[dict[str, object]]:
    return [
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
    ]


def build_notification_messages(
    *,
    context: CommunicationContext,
    candidates: list[NotificationCandidate],
) -> list[dict[str, object]]:
    return [
        _message("system", IDENTITY_PROMPT),
        _message("system", REPLY_STYLE_PROMPT),
        _message("system", GUARDRAILS_PROMPT),
        _message("system", PROACTIVE_NOTIFICATION_PROMPT),
        _message("system", NOTIFICATION_STYLE_EXAMPLES_PROMPT),
        _message("system", json.dumps(build_runtime_context(context))),
        _message("system", json.dumps(build_notification_candidates_payload(candidates))),
        *[_message(entry.role, entry.text) for entry in context.recent_history],
    ]


def _message(role: str, text: str) -> dict[str, object]:
    return {"role": role, "content": text}
