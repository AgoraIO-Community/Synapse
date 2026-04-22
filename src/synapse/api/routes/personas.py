from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from synapse.api.models import PersonaCreateRequest, PersonaUpdateRequest
from synapse.communication.persona_pool import load_personas_from_file, save_personas_to_file
from synapse.protocol import Persona

router = APIRouter()


@router.get("/sessions/{session_id}/personas")
async def list_personas(session_id: str, request: Request):
    container = request.app.state.runtime_container
    try:
        container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return load_personas_from_file()


@router.post("/sessions/{session_id}/personas", status_code=201)
async def create_persona(
    session_id: str,
    body: PersonaCreateRequest,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    persona_id = f"persona-{body.name.lower().replace(' ', '-')}"
    personas = load_personas_from_file()
    if any(persona.persona_id == persona_id for persona in personas):
        raise HTTPException(status_code=409, detail=f"Persona '{body.name}' already exists.")
    persona = Persona(
        persona_id=persona_id,
        name=body.name,
        avatar=body.avatar,
        base_prompt=body.base_prompt,
    )
    save_personas_to_file([*personas, persona])
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
        container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    personas = load_personas_from_file()
    persona = next((item for item in personas if item.persona_id == persona_id), None)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found.")
    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.avatar is not None:
        updates["avatar"] = body.avatar
    if body.base_prompt is not None:
        updates["base_prompt"] = body.base_prompt
    updated = persona.model_copy(update=updates) if updates else persona
    if updates:
        save_personas_to_file(
            [
                updated if item.persona_id == persona_id else item
                for item in personas
            ]
        )
    return updated


@router.delete("/sessions/{session_id}/personas/{persona_id}")
async def delete_persona(
    session_id: str,
    persona_id: str,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    personas = load_personas_from_file()
    persona = next((item for item in personas if item.persona_id == persona_id), None)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found.")
    save_personas_to_file([item for item in personas if item.persona_id != persona_id])
    return {"deleted": persona_id}
