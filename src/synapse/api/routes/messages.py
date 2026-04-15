from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from synapse.api.models import MessageRequest, MessageResponse, ToolInvocationSummary

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

    request_id = f"http-msg-{uuid4().hex[:8]}"
    _, completion = await session.submit_message(
        request_id,
        request.text,
        start_processing=False,
    )
    session.observability.api.message_accepted(
        conversation_id=session.session_id,
        request_id=request_id,
        transport="http",
    )
    await session.publish_snapshot()
    session.start_message_processing()
    result = await completion
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
