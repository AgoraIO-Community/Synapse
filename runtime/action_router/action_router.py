from __future__ import annotations

from runtime.protocols.trace import TraceStage
from runtime.llm.message_interpreter import MessageInterpreterClient
from runtime.protocols.conversation import UserMessage
from runtime.protocols.runtime import ActionBundle, RoutingDecision
from runtime.protocols.stream import SessionSnapshot
from runtime.shared_blackboard.trace_state import TraceStateStore


class ActionRouter:
    def __init__(
        self,
        message_interpreter: MessageInterpreterClient,
        trace_state_store: TraceStateStore,
    ) -> None:
        self._message_interpreter = message_interpreter
        self._trace_state_store = trace_state_store

    def route(
        self,
        user_message: UserMessage,
        snapshot: SessionSnapshot,
        *,
        span_id: str | None = None,
    ) -> tuple[RoutingDecision, ActionBundle]:
        import asyncio

        asyncio.create_task(
            self._trace_state_store.publish(
                user_message.session_id,
                TraceStage.ACTION_ROUTER,
                "routing_started",
                "action_router",
                {"text": user_message.text},
                span_id=span_id,
                related_message_id=user_message.message_id,
            )
        )
        decision, bundle = self._message_interpreter.interpret(
            session_id=user_message.session_id,
            message_id=user_message.message_id,
            text=user_message.text,
            snapshot=snapshot,
            span_id=span_id,
        )
        asyncio.create_task(
            self._trace_state_store.publish(
                user_message.session_id,
                TraceStage.ACTION_ROUTER,
                "routing_completed",
                "action_router",
                {
                    "needs_clarification": decision.needs_clarification,
                    "action_count": len(bundle.actions),
                },
                span_id=span_id,
                related_message_id=user_message.message_id,
            )
        )
        return decision, bundle
