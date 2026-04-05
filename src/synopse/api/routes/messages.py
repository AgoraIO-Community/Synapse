from fastapi import APIRouter, HTTPException, Request

from synopse.api.models import MessageRequest, MessageResponse, ToolInvocationSummary

router = APIRouter()


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def submit_message(
    session_id: str,
    request: MessageRequest,
    http_request: Request,
) -> MessageResponse:
    container = http_request.app.state.runtime_container
    try:
        session = container.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = await session.communication_brain.handle_user_message(session_id, request.text)
    await session.execution_brain.tick()
    await session.publish_snapshot()
    return MessageResponse(
        message_id=result.message_id,
        reply_text=result.reply_text,
        conversational_act=result.conversational_act,
        affected_task_ids=result.affected_task_ids,
        tool_invocations=[
            ToolInvocationSummary(tool_name=item.tool_name, args=item.args)
            for item in result.tool_invocations
        ],
    )
