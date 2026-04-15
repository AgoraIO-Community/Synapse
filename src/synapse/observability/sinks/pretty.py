from __future__ import annotations

import sys
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
