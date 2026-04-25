from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from synapse.protocol import DraftSession
from synapse.runtime.drafts import (
    DraftRewriteInvalidOutput,
    DraftRewriteUnavailable,
    DraftRewriteUpstreamError,
)

router = APIRouter()


class AsrTurnRequest(BaseModel):
    raw_text: str
    normalized_text: str | None = None
    confidence: float | None = None
    started_at: str | None = None
    ended_at: str | None = None
    assigned_bro_id: str | None = None


class SendDraftRequest(BaseModel):
    draft_session_id: str | None = None


class SendDraftResponse(BaseModel):
    task_id: str
    draft_session_id: str
    draft_snapshot_id: str


class ClearDraftRequest(BaseModel):
    draft_session_id: str | None = None


class ClearDraftResponse(BaseModel):
    status: str = "cleared"


@router.get("/sessions/{session_id}/draft", response_model=DraftSession | None)
async def get_draft(session_id: str, http_request: Request) -> DraftSession | None:
    session = _get_session(http_request, session_id)
    return session.draft_manager.active_session


@router.post("/sessions/{session_id}/draft/asr-turns", response_model=DraftSession)
async def submit_asr_turn(
    session_id: str,
    request: AsrTurnRequest,
    http_request: Request,
) -> DraftSession:
    session = _get_session(http_request, session_id)
    try:
        draft_session = await session.append_asr_turn_to_draft(
            raw_text=request.raw_text,
            normalized_text=request.normalized_text,
            confidence=request.confidence,
            started_at=request.started_at,
            ended_at=request.ended_at,
            assigned_bro_id=request.assigned_bro_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DraftRewriteUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DraftRewriteUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DraftRewriteInvalidOutput as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await session.publish_snapshot()
    return draft_session


@router.post("/sessions/{session_id}/draft/send", response_model=SendDraftResponse)
async def send_draft(
    session_id: str,
    request: SendDraftRequest,
    http_request: Request,
) -> SendDraftResponse:
    session = _get_session(http_request, session_id)
    try:
        task = await session.send_draft(draft_session_id=request.draft_session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.publish_snapshot()
    session.schedule_execution()
    return SendDraftResponse(
        task_id=task.task_id,
        draft_session_id=str(task.metadata["draft_session_id"]),
        draft_snapshot_id=str(task.metadata["draft_snapshot_id"]),
    )


@router.post("/sessions/{session_id}/draft/clear", response_model=ClearDraftResponse)
async def clear_draft(
    session_id: str,
    request: ClearDraftRequest,
    http_request: Request,
) -> ClearDraftResponse:
    session = _get_session(http_request, session_id)
    active = session.draft_manager.active_session
    if request.draft_session_id is not None and active is not None and active.id != request.draft_session_id:
        raise HTTPException(status_code=409, detail="Draft session does not match the active draft.")
    session.clear_draft()
    await session.publish_snapshot()
    return ClearDraftResponse()


def _get_session(http_request: Request, session_id: str):
    container = http_request.app.state.runtime_container
    try:
        return container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
