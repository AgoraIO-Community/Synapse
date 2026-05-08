from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from newbro.api.auth import require_http_api_auth
from newbro.api.models import ExecutorNodeCreateRequest, ExecutorNodeUpdateRequest

router = APIRouter()


def _require_session(container, session_id: str):
    try:
        return container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/executor-nodes")
async def list_executor_nodes(session_id: str, request: Request):
    require_http_api_auth(request)
    container = request.app.state.runtime_container
    _require_session(container, session_id)
    return await container.executor_node_manager.list_nodes()


@router.post("/sessions/{session_id}/executor-nodes", status_code=201)
async def create_executor_node(
    session_id: str,
    body: ExecutorNodeCreateRequest,
    request: Request,
):
    require_http_api_auth(request)
    container = request.app.state.runtime_container
    _require_session(container, session_id)
    try:
        issue = await container.executor_node_manager.create_node(
            name=body.name,
            enabled_executors=body.enabled_executors,
            acpx_agent=body.acpx_agent,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await container.publish_session_snapshots()
    return issue


@router.patch("/sessions/{session_id}/executor-nodes/{node_id}")
async def update_executor_node(
    session_id: str,
    node_id: str,
    body: ExecutorNodeUpdateRequest,
    request: Request,
):
    require_http_api_auth(request)
    container = request.app.state.runtime_container
    _require_session(container, session_id)
    try:
        record = await container.executor_node_manager.update_node(
            node_id,
            name=body.name if "name" in body.model_fields_set else None,
            enabled_executors=body.enabled_executors if "enabled_executors" in body.model_fields_set else None,
            acpx_agent=body.acpx_agent if "acpx_agent" in body.model_fields_set else None,
        )
    except RuntimeError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await container.publish_session_snapshots()
    return record


@router.post("/sessions/{session_id}/executor-nodes/{node_id}/credentials/rotate")
async def rotate_executor_node_credentials(
    session_id: str,
    node_id: str,
    request: Request,
):
    require_http_api_auth(request)
    container = request.app.state.runtime_container
    _require_session(container, session_id)
    try:
        issue = await container.executor_node_manager.rotate_node_credentials(node_id)
    except RuntimeError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await container.publish_session_snapshots()
    return issue


@router.post("/sessions/{session_id}/executor-nodes/{node_id}/connect-command")
async def reveal_executor_node_connect_command(
    session_id: str,
    node_id: str,
    request: Request,
):
    require_http_api_auth(request)
    container = request.app.state.runtime_container
    _require_session(container, session_id)
    try:
        issue = await container.executor_node_manager.reveal_node_credentials(node_id)
    except RuntimeError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            status_code = 404
        elif "rotate credentials first" in lowered or "legacy non-retrievable" in lowered:
            status_code = 409
        else:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return issue


@router.delete("/sessions/{session_id}/executor-nodes/{node_id}")
async def delete_executor_node(
    session_id: str,
    node_id: str,
    request: Request,
):
    require_http_api_auth(request)
    container = request.app.state.runtime_container
    _require_session(container, session_id)
    bound_personas = await container.bound_persona_names_for_node(node_id)
    if bound_personas:
        raise HTTPException(
            status_code=409,
            detail=f"Executor node '{node_id}' is still bound to bros: {', '.join(bound_personas)}.",
        )
    deleted = await container.executor_node_manager.delete_node(node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Executor node '{node_id}' not found.")
    await container.publish_session_snapshots()
    return {"deleted": node_id}
