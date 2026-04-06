from fastapi import APIRouter, HTTPException, Request

from synopse.api.models import SessionResponse

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: Request,
) -> SessionResponse:
    container = request.app.state.runtime_container
    session = container.create_session()
    return SessionResponse(session_id=session.session_id)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await session.snapshot()


@router.get("/sessions/{session_id}/conversation")
async def get_session_conversation(
    session_id: str,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await session.conversation_snapshot()


@router.get("/sessions/{session_id}/debug")
async def get_session_debug(
    session_id: str,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await session.debug_snapshot()


@router.get("/sessions/{session_id}/tasks")
async def list_tasks(
    session_id: str,
    request: Request,
):
    container = request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await session.blackboard.list_tasks()
