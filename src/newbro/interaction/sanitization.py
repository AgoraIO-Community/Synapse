from __future__ import annotations

from copy import deepcopy


_CLIENT_SAFE_NATIVE_RESPONSE_PARAM_KEYS = (
    "threadId",
    "turnId",
    "itemId",
    "reason",
    "command",
)
_CLIENT_SAFE_BLOCKED_EVENT_KEYS = (
    "thread_id",
    "prompt",
    "interaction_kind",
    "blocked_method",
)


def build_interaction_request_opaque(*, blocked_event: object) -> dict[str, object]:
    if not isinstance(blocked_event, dict):
        return {}
    native_response = blocked_event.get("native_response")
    if not isinstance(native_response, dict):
        return {}
    return {"native_response": deepcopy(native_response)}


def sanitize_interaction_request_opaque(opaque: dict[str, object]) -> dict[str, object]:
    native_response = _sanitize_native_response_for_client(opaque.get("native_response"))
    return {"native_response": native_response} if native_response else {}


def sanitize_interaction_request_details(details: dict[str, object]) -> dict[str, object]:
    sanitized = dict(details)
    blocked_event = sanitize_blocked_event_for_client(details.get("blocked_event"))
    if blocked_event is None:
        sanitized.pop("blocked_event", None)
    else:
        sanitized["blocked_event"] = blocked_event
    return sanitized


def sanitize_blocked_event_for_client(blocked_event: object) -> dict[str, object] | None:
    if not isinstance(blocked_event, dict):
        return None
    sanitized: dict[str, object] = {}
    for key in _CLIENT_SAFE_BLOCKED_EVENT_KEYS:
        value = blocked_event.get(key)
        if value is not None:
            sanitized[key] = value
    native_response = _sanitize_native_response_for_client(blocked_event.get("native_response"))
    if native_response:
        sanitized["native_response"] = native_response
    return sanitized or None


def _sanitize_native_response_for_client(native_response: object) -> dict[str, object] | None:
    if not isinstance(native_response, dict):
        return None
    sanitized: dict[str, object] = {}
    for key in ("request_id", "method"):
        value = native_response.get(key)
        if value is not None:
            sanitized[key] = value
    params = native_response.get("params")
    if isinstance(params, dict):
        sanitized_params: dict[str, object] = {}
        for key in _CLIENT_SAFE_NATIVE_RESPONSE_PARAM_KEYS:
            value = params.get(key)
            if isinstance(value, str) and value:
                sanitized_params[key] = value
        if sanitized_params:
            sanitized["params"] = sanitized_params
    return sanitized or None
