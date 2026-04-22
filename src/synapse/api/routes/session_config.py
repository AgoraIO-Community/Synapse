from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from synapse.communication.persona_pool import (
    load_communication_persona_prompt_from_file,
    save_communication_persona_prompt_to_file,
)

router = APIRouter()

ALLOWED_CONFIG_KEYS = frozenset({
    "communication_persona_prompt",
})
_LOAD_HOOKS: dict[str, Callable[[], str]] = {
    "communication_persona_prompt": load_communication_persona_prompt_from_file,
}
_PERSIST_HOOKS: dict[str, Callable[[str], None]] = {
    "communication_persona_prompt": save_communication_persona_prompt_to_file,
}


class SessionConfigValue(BaseModel):
    value: str


def _validate_key(key: str) -> None:
    if key not in ALLOWED_CONFIG_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown config key '{key}'. Allowed keys: {', '.join(sorted(ALLOWED_CONFIG_KEYS))}",
        )


@router.get("/sessions/{session_id}/config/{key}")
async def get_session_config(session_id: str, key: str, request: Request):
    _validate_key(key)
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    del session
    loader = _LOAD_HOOKS[key]
    value = loader()
    return {"key": key, "value": value}


@router.put("/sessions/{session_id}/config/{key}")
async def put_session_config(
    session_id: str,
    key: str,
    body: SessionConfigValue,
    request: Request,
):
    _validate_key(key)
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    del session
    persist_hook = _PERSIST_HOOKS[key]
    persist_hook(body.value)
    return {"key": key, "value": body.value}
