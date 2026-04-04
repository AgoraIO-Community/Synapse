from fastapi import APIRouter, Depends, HTTPException

from runtime.api.deps import get_services
from runtime.api.models import CommandRequest
from runtime.infrastructure.ids import new_id
from runtime.protocols.tasks import ControlCommand

router = APIRouter()


@router.post("/sessions/{session_id}/commands")
async def submit_command(
    session_id: str, request: CommandRequest, services=Depends(get_services)
):
    try:
        services.store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    command = ControlCommand(
        command_id=new_id("cmd"),
        target_task_ref=request.effective_reference(),
        target_task_id=request.target_task_id,
        command_type=request.command_type,
        payload=request.payload,
        reason=request.reason,
    )
    await services.execution_orchestrator.apply_control_command(session_id, command)
    return {"command_id": command.command_id, "status": "accepted"}
