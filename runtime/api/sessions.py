from fastapi import APIRouter, Depends, HTTPException

from runtime.api.deps import get_services
from runtime.api.models import SessionResponse

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(services=Depends(get_services)) -> SessionResponse:
    session = services.runtime_state_store.create_session()
    services.trace_state_store.ensure_session(session.session_id)
    return SessionResponse(session_id=session.session_id)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, services=Depends(get_services)):
    try:
        return services.runtime_state_store.snapshot(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/tasks")
async def list_tasks(session_id: str, services=Depends(get_services)):
    try:
        snapshot = services.runtime_state_store.snapshot(session_id)
        return snapshot.task_registry
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
