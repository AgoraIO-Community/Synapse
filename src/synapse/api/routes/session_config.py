from __future__ import annotations

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
        container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Read from the persisted file, not the live blackboard.
    # The blackboard value is frozen at session start.
    if key == "communication_persona_prompt":
        value = load_communication_persona_prompt_from_file()
    else:
        value = None
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
        container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Persist to file only. The current session's blackboard is not updated;
    # the new value takes effect on the next session start.
    if key == "communication_persona_prompt":
        save_communication_persona_prompt_to_file(body.value)
    return {"key": key, "value": body.value}
