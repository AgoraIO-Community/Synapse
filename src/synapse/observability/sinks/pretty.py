from __future__ import annotations

import json
import sys
import textwrap
from datetime import datetime
from typing import TextIO

from ..schema import DiagnosticEvent
from .types import DiagnosticSink


RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"

LEVEL_COLORS = {
    "DEBUG": DIM + "\033[37m",
    "INFO": "\033[36m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": BOLD + "\033[31m",
}

MAX_DETAILS = 4
MAX_VALUE_LENGTH = 36


class PrettyDiagnosticSink(DiagnosticSink):
    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        color_enabled: bool = True,
    ) -> None:
        self._stream = stream or sys.stdout
        self._color_enabled = color_enabled

    def emit(self, event: DiagnosticEvent) -> None:
        self._stream.write(render_pretty_event(event, color_enabled=self._color_enabled) + "\n")
        self._stream.flush()


def render_pretty_event(
    event: DiagnosticEvent,
    *,
    color_enabled: bool,
) -> str:
    if event.event_name == "comm.llm.request_built":
        return _render_comm_llm_request_built(event, color_enabled=color_enabled)

    return _render_compact_event(event, color_enabled=color_enabled)


def _render_compact_event(
    event: DiagnosticEvent,
    *,
    color_enabled: bool,
) -> str:
    parts = [
        _render_timestamp(event.ts),
        _render_level(event.level, color_enabled=color_enabled),
        event.event_name,
        event.summary,
    ]

    for label, value in (
        ("conversation", event.conversation_id),
        ("request", event.request_id),
        ("task", event.task_id),
        ("run", event.run_id),
        ("exec_session", event.execution_session_id),
        ("notification", event.notification_id),
        ("executor", event.executor_type),
    ):
        if value:
            parts.append(f"{label}={value}")

    if event.outcome:
        parts.append(f"outcome={event.outcome}")
    if event.reason_code:
        parts.append(f"reason={event.reason_code}")

    detail_items = list(event.details.items())
    if detail_items:
        rendered_details = [
            f"{key}={_render_value(value)}"
            for key, value in detail_items[:MAX_DETAILS]
        ]
        if len(detail_items) > MAX_DETAILS:
            rendered_details.append("...")
        parts.append("details[" + " ".join(rendered_details) + "]")

    return " ".join(parts)


def _render_comm_llm_request_built(
    event: DiagnosticEvent,
    *,
    color_enabled: bool,
) -> str:
    lines = [_render_compact_event(_event_without_details(event), color_enabled=color_enabled)]
    details = event.details

    prompt_sections = details.get("prompt_sections")
    if isinstance(prompt_sections, list) and prompt_sections:
        lines.append(_render_detail_line("prompt_sections", ", ".join(str(item) for item in prompt_sections)))

    available_tools = details.get("available_tools")
    if isinstance(available_tools, list) and available_tools:
        lines.append(_render_detail_line("available_tools", ", ".join(str(item) for item in available_tools)))

    system_messages = details.get("system_messages")
    if isinstance(system_messages, list) and system_messages:
        for index, message in enumerate(system_messages):
            if not isinstance(message, dict):
                continue
            label = _system_message_label(index=index, message=message, prompt_sections=prompt_sections)
            content = message.get("content")
            if not isinstance(content, str):
                continue
            lines.extend(_render_system_message_block(label=label, content=content))

    return "\n".join(lines)


def _event_without_details(event: DiagnosticEvent) -> DiagnosticEvent:
    return event.model_copy(update={"details": {}})


def _render_detail_line(label: str, value: str) -> str:
    return f"  {label}: {value}"


def _system_message_label(
    *,
    index: int,
    message: dict[str, object],
    prompt_sections: object,
) -> str:
    if isinstance(prompt_sections, list) and index < len(prompt_sections):
        section = prompt_sections[index]
        if isinstance(section, str) and section:
            return f"system[{index}:{section}]"
    role = message.get("role")
    if isinstance(role, str) and role:
        return f"system[{index}:{role}]"
    return f"system[{index}]"


def _render_system_message_block(*, label: str, content: str) -> list[str]:
    lines = [f"  {label}:"]
    parsed_json = _try_parse_json(content)
    if parsed_json is not None:
        pretty_json = json.dumps(parsed_json, indent=2, ensure_ascii=True)
        lines.extend(f"    {line}" for line in pretty_json.splitlines())
        return lines

    wrapped = textwrap.wrap(
        content,
        width=100,
        replace_whitespace=False,
        drop_whitespace=False,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped:
        lines.append("    ")
        return lines
    lines.extend(f"    {line}" for line in wrapped)
    return lines


def _try_parse_json(value: str) -> object | None:
    stripped = value.strip()
    if not stripped.startswith("{") and not stripped.startswith("["):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _render_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%H:%M:%S.%f")[:-3]


def _render_level(level: str, *, color_enabled: bool) -> str:
    token = f"{level:<8}"
    if not color_enabled:
        return token
    color = LEVEL_COLORS.get(level)
    if color is None:
        return token
    return f"{color}{token}{RESET}"


def _render_value(value: object) -> str:
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) or value is None:
        return str(value)
    if isinstance(value, list):
        return _truncate(",".join(_render_value(item) for item in value))
    if isinstance(value, dict):
        keys = ",".join(sorted(str(key) for key in value.keys())[:4])
        return "{keys=" + _truncate(keys) + "}"
    return _truncate(str(value))


def _truncate(value: str) -> str:
    if len(value) <= MAX_VALUE_LENGTH:
        return value
    return value[: MAX_VALUE_LENGTH - 3] + "..."
