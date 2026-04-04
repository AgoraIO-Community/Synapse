from fastapi import APIRouter, Depends, HTTPException

from runtime.api.deps import get_services
from runtime.api.models import MessageRequest, MessageResponse
from runtime.infrastructure.ids import new_id
from runtime.llm.errors import LLMConfigurationError, LLMInvocationError
from runtime.protocols.conversation import UserMessage
from runtime.protocols.runtime import ActionBundle, ConversationMode, RuntimeActionType
from runtime.protocols.trace import TraceStage
from runtime.shared_blackboard.mutations import append_message_history

router = APIRouter()


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def submit_message(
    session_id: str, request: MessageRequest, services=Depends(get_services)
) -> MessageResponse:
    try:
        session = services.runtime_state_store.get_session(session_id)
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
    append_message_history(
        session,
        role="user",
        text=message.text,
        message_id=message.message_id,
        timestamp=message.timestamp,
    )
    snapshot = services.runtime_state_store.snapshot(session_id)
    span_id = new_id("span")
    try:
        await services.trace_state_store.publish(
            session_id,
            TraceStage.API,
            "message_received",
            "api.messages",
            {
                "text": request.text,
                "modality": request.modality.value,
                "task_count": len(snapshot.task_registry),
            },
            span_id=span_id,
            related_message_id=message.message_id,
        )
        routing_decision, bundle = await services.action_router.route(
            message,
            snapshot,
            span_id=span_id,
        )

        initial_action = services.interaction_policy.build_initial_action(
            routing_decision,
            bundle,
            user_message_text=message.text,
        )
        await services.trace_state_store.publish(
            session_id,
            TraceStage.INTERACTION_POLICY,
            "initial_interaction_selected",
            "interaction_policy",
            {
                "action_type": initial_action.action_type.value,
                "needs_clarification": routing_decision.needs_clarification,
            },
            span_id=span_id,
            related_message_id=message.message_id,
        )
        await services.execution_orchestrator.emit_conversation_action(
            session_id,
            initial_action,
            related_message_id=message.message_id,
            span_id=span_id,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMInvocationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if routing_decision.conversation_mode == ConversationMode.CLARIFICATION or routing_decision.needs_clarification:
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
    elif routing_decision.conversation_mode == ConversationMode.CONVERSATION_ONLY:
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

    try:
        if bundle.actions:
            await services.execution_orchestrator.process_bundle(
                session_id,
                bundle,
                span_id=span_id,
            )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMInvocationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MessageResponse(
        message_id=message.message_id,
        routing_decision=routing_decision.model_dump(mode="json"),
        action_bundle=bundle.model_dump(mode="json"),
    )
