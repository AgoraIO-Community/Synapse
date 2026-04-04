from fastapi import APIRouter, Depends, HTTPException

from runtime.api.deps import get_services
from runtime.api.models import MessageRequest, MessageResponse
from runtime.infrastructure.ids import new_id
from runtime.protocols.conversation import UserMessage
from runtime.protocols.runtime import ActionBundle, RuntimeActionType

router = APIRouter()


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def submit_message(
    session_id: str, request: MessageRequest, services=Depends(get_services)
) -> MessageResponse:
    try:
        snapshot = services.store.snapshot(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    message = UserMessage(
        message_id=new_id("message"),
        session_id=session_id,
        text=request.text,
        modality=request.modality,
        interrupts_current_output=request.interrupts_current_output,
        metadata=request.metadata,
    )
    routing_decision, bundle = services.message_router.route(message, snapshot)

    initial_action = services.communication_interpreter.build_initial_action(
        routing_decision, bundle
    )
    await services.execution_orchestrator.emit_conversation_action(
        session_id,
        initial_action,
        related_message_id=message.message_id,
    )

    if routing_decision.needs_clarification:
        safe_actions = [
            action
            for action in bundle.actions
            if action.action_type == RuntimeActionType.APPLY_CONTEXT_PATCH
        ]
        bundle = ActionBundle(
            bundle_id=bundle.bundle_id,
            message_id=bundle.message_id,
            actions=safe_actions,
            relations=bundle.relations,
        )

    await services.execution_orchestrator.process_bundle(session_id, bundle)
    return MessageResponse(
        message_id=message.message_id,
        routing_decision=routing_decision.model_dump(mode="json"),
        action_bundle=bundle.model_dump(mode="json"),
    )
