from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from synapse.api.models import PersonaCreateRequest, PersonaUpdateRequest
from synapse.communication.persona_pool import save_personas_to_file
from synapse.protocol import Persona

router = APIRouter()


@router.get("/sessions/{session_id}/personas")
async def list_personas(session_id: str, request: Request):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await session.blackboard.list_personas()


@router.post("/sessions/{session_id}/personas", status_code=201)
async def create_persona(
    session_id: str,
    body: PersonaCreateRequest,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    persona_id = f"persona-{body.name.lower().replace(' ', '-')}"
    existing = await session.blackboard.get_persona(persona_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Persona '{body.name}' already exists.")
    persona = Persona(
        persona_id=persona_id,
        name=body.name,
        avatar=body.avatar,
        base_prompt=body.base_prompt,
    )
    await session.blackboard.put_persona(persona)
    await _persist_personas(session)
    return persona


@router.patch("/sessions/{session_id}/personas/{persona_id}")
async def update_persona(
    session_id: str,
    persona_id: str,
    body: PersonaUpdateRequest,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    persona = await session.blackboard.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found.")
    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.avatar is not None:
        updates["avatar"] = body.avatar
    if body.base_prompt is not None:
        updates["base_prompt"] = body.base_prompt
    if updates:
        await session.blackboard.put_persona(persona.model_copy(update=updates))
    await _persist_personas(session)
    return await session.blackboard.get_persona(persona_id)


@router.delete("/sessions/{session_id}/personas/{persona_id}")
async def delete_persona(
    session_id: str,
    persona_id: str,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    persona = await session.blackboard.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found.")
    if persona.status == "busy":
        raise HTTPException(status_code=409, detail=f"{persona.name} is busy. Cancel the task first.")
    await session.blackboard.delete_persona(persona_id)
    await _persist_personas(session)
    return {"deleted": persona_id}


async def _persist_personas(session) -> None:
    """Write current personas back to ~/.synapse/personas.yaml."""
    personas = await session.blackboard.list_personas()
    save_personas_to_file(personas)
