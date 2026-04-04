from __future__ import annotations

from pydantic import ValidationError

from runtime.llm.errors import LLMInvocationError
from runtime.llm.interpreter_schema import (
    InterpretationEnvelope,
    to_runtime_action_bundle,
    to_runtime_routing_decision,
)
from runtime.llm.openai_client import OpenAIProvider
from runtime.llm.prompts import build_interpreter_input, build_interpreter_instructions
from runtime.protocols.runtime import ActionBundle, RoutingDecision
from runtime.protocols.stream import SessionSnapshot
from runtime.protocols.trace import TraceStage
from runtime.shared_blackboard.trace_state import TraceStateStore


class MessageInterpreterClient:
    def __init__(
        self,
        provider: OpenAIProvider | None = None,
        trace_state_store: TraceStateStore | None = None,
    ) -> None:
        self._provider = provider
        self._trace_state_store = trace_state_store

    async def interpret(
        self,
        *,
        session_id: str,
        message_id: str,
        text: str,
        snapshot: SessionSnapshot,
        span_id: str | None = None,
    ) -> tuple[RoutingDecision, ActionBundle]:
        if self._provider is None:
            raise LLMInvocationError("Message interpreter is missing its OpenAI provider.")

        if self._trace_state_store:
            await self._trace_state_store.publish(
                session_id,
                TraceStage.MESSAGE_INTERPRETER,
                "interpreter_request_started",
                "message_interpreter",
                {"text": text},
                span_id=span_id,
                related_message_id=message_id,
            )
        parsed = await self._provider.parse_structured(
            instructions=build_interpreter_instructions(),
            input_text=build_interpreter_input(
                message_id=message_id,
                text=text,
                snapshot=snapshot,
            ),
            schema=InterpretationEnvelope,
            trace_state_store=self._trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=message_id,
        )
        if self._trace_state_store:
            await self._trace_state_store.publish(
                session_id,
                TraceStage.MESSAGE_INTERPRETER,
                "interpreter_response_received",
                "message_interpreter",
                {
                    "action_count": len(parsed.action_bundle.actions),
                    "needs_clarification": parsed.routing_decision.needs_clarification,
                },
                span_id=span_id,
                related_message_id=message_id,
            )
        if parsed.routing_decision.message_id != message_id:
            raise LLMInvocationError("Interpreter returned a routing_decision for the wrong message_id.")
        if parsed.action_bundle.message_id != message_id:
            raise LLMInvocationError("Interpreter returned an action_bundle for the wrong message_id.")
        try:
            routing_decision = to_runtime_routing_decision(parsed.routing_decision)
            action_bundle = to_runtime_action_bundle(parsed.action_bundle)
        except (ValidationError, ValueError, TypeError) as exc:
            raise LLMInvocationError(
                f"Interpreter returned invalid runtime action payload: {exc}"
            ) from exc
        if self._trace_state_store:
            await self._trace_state_store.publish(
                session_id,
                TraceStage.MESSAGE_INTERPRETER,
                "interpreter_converted",
                "message_interpreter",
                {
                    "runtime_action_count": len(action_bundle.actions),
                    "needs_clarification": routing_decision.needs_clarification,
                },
                span_id=span_id,
                related_message_id=message_id,
            )
        return (
            routing_decision,
            action_bundle,
        )
