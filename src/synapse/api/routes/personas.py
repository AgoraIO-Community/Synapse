from __future__ import annotations

from uuid import uuid4

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
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Persona name is required.")
    if body.executor_node_id is not None and not await container.executor_node_manager.node_exists(body.executor_node_id):
        raise HTTPException(status_code=400, detail=f"Executor node '{body.executor_node_id}' not found.")
    normalized_name = body.name.strip()
    persona_id = _generated_persona_id(normalized_name)
    personas = load_personas_from_file()
    persona = Persona(
        persona_id=persona_id,
        name=normalized_name,
        avatar=body.avatar,
        base_prompt=body.base_prompt,
        executor_node_id=body.executor_node_id,
    )
    updated_personas = [*personas, persona]
    save_personas_to_file(updated_personas)
    await container.sync_persisted_personas(updated_personas)
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
    if "name" in body.model_fields_set:
        if body.name is None or not body.name.strip():
            raise HTTPException(status_code=400, detail="Persona name is required.")
        updates["name"] = body.name.strip()
    if "avatar" in body.model_fields_set:
        if body.avatar is None:
            raise HTTPException(status_code=400, detail="Persona avatar is required.")
        updates["avatar"] = body.avatar
    if "base_prompt" in body.model_fields_set:
        if body.base_prompt is None:
            raise HTTPException(status_code=400, detail="Persona base prompt is required.")
        updates["base_prompt"] = body.base_prompt
    if "executor_node_id" in body.model_fields_set:
        if body.executor_node_id is not None and not await container.executor_node_manager.node_exists(body.executor_node_id):
            raise HTTPException(status_code=400, detail=f"Executor node '{body.executor_node_id}' not found.")
        updates["executor_node_id"] = body.executor_node_id
        if body.executor_node_id != persona.executor_node_id:
            updates["bro_detail_session_id"] = _generated_bro_detail_session_id()
    updated = persona.model_copy(update=updates) if updates else persona
    if updates:
        updated_personas = [
            updated if item.persona_id == persona_id else item
            for item in personas
        ]
        save_personas_to_file(updated_personas)
        await container.sync_persisted_personas(updated_personas)
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
    if await container.persona_is_busy(persona_id):
        raise HTTPException(status_code=409, detail=f"Persona '{persona_id}' is busy and cannot be deleted.")
    updated_personas = [item for item in personas if item.persona_id != persona_id]
    save_personas_to_file(updated_personas)
    await container.sync_persisted_personas(updated_personas)
    return {"deleted": persona_id}


def _generated_persona_id(name: str) -> str:
    slug = "-".join(name.strip().lower().split())
    return f"persona-{slug or 'bro'}-{uuid4().hex[:8]}"


def _generated_bro_detail_session_id() -> str:
    return f"bro-detail-{uuid4().hex[:8]}"
