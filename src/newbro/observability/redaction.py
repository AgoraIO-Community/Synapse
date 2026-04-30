from __future__ import annotations

from typing import Any


REDACTED = "[redacted]"
SENSITIVE_KEY_PARTS = {
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
}
TEXT_PREVIEW_KEYS = {
    "content",
    "delta",
    "message",
    "prompt",
    "reply_text",
    "summary",
    "text",
    "user_text",
}


def sanitize_details(
    value: dict[str, Any] | None,
    *,
    debug_enabled: bool = False,
) -> dict[str, Any]:
    if not value:
        return {}
    return _sanitize_mapping(value, debug_enabled=debug_enabled)


def _sanitize_mapping(
    value: dict[str, Any],
    *,
    debug_enabled: bool,
    preserve_full_text: bool = False,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        sanitized[key] = _sanitize_value(
            key,
            item,
            debug_enabled=debug_enabled,
            preserve_full_text=preserve_full_text,
        )
    return sanitized


def _sanitize_value(
    key: str,
    value: Any,
    *,
    debug_enabled: bool,
    preserve_full_text: bool = False,
) -> Any:
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return REDACTED
    if isinstance(value, dict):
        return _sanitize_mapping(
            value,
            debug_enabled=debug_enabled,
            preserve_full_text=preserve_full_text,
        )
    if isinstance(value, list):
        child_preserve_full_text = preserve_full_text or lowered == "system_messages"
        return [
            _sanitize_value(
                key,
                item,
                debug_enabled=debug_enabled,
                preserve_full_text=child_preserve_full_text,
            )
            for item in value[:20]
        ]
    if isinstance(value, tuple):
        return [
            _sanitize_value(
                key,
                item,
                debug_enabled=debug_enabled,
                preserve_full_text=preserve_full_text,
            )
            for item in value[:20]
        ]
    if isinstance(value, str):
        return _sanitize_text(
            lowered,
            value,
            debug_enabled=debug_enabled,
            preserve_full_text=preserve_full_text,
        )
    return value


def _sanitize_text(
    key: str,
    value: str,
    *,
    debug_enabled: bool,
    preserve_full_text: bool = False,
) -> str:
    if preserve_full_text:
        return value
    if debug_enabled:
        return value[:500]
    if key in TEXT_PREVIEW_KEYS or key.endswith("_text") or key.endswith("_message"):
        if len(value) <= 80:
            return value
        return value[:77] + "..."
    if len(value) <= 160:
        return value
    return value[:157] + "..."
