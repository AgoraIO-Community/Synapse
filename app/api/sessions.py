from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_services
from app.api.models import SessionResponse

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(services=Depends(get_services)) -> SessionResponse:
    session = services.store.create_session()
    return SessionResponse(session_id=session.session_id)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, services=Depends(get_services)):
    try:
        return services.store.snapshot(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/tasks")
async def list_tasks(session_id: str, services=Depends(get_services)):
    try:
        snapshot = services.store.snapshot(session_id)
        return snapshot.task_registry
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
