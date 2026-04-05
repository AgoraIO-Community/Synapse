from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from synopse.api.models import CommandRequest, CommandResponse
from synopse.communication.resolver import TaskResolver
from synopse.protocol import TaskCommand

router = APIRouter()


@router.post("/sessions/{session_id}/commands", response_model=CommandResponse)
async def submit_command(
    session_id: str,
    request: CommandRequest,
    http_request: Request,
) -> CommandResponse:
    container = http_request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    tasks = await session.blackboard.list_tasks()
    task = TaskResolver().resolve(tasks, task_id=request.task_id, reference=request.reference)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    command = TaskCommand(
        command_id=f"cmd-{uuid4().hex[:8]}",
        task_id=task.task_id,
        command_type=request.command_type,
        payload=request.payload,
        created_by="api",
        reason=request.reason,
    )
    await session.apply_command(command)
    session.schedule_execution()
    await session.publish_snapshot()
    return CommandResponse(command_id=command.command_id, affected_task_ids=[task.task_id])
