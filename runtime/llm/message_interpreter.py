from __future__ import annotations

import asyncio
import re

from runtime.infrastructure.ids import new_id
from runtime.llm.errors import LLMInvocationError
from runtime.llm.interpreter_schema import (
    InterpretationEnvelope,
    InterpreterAction,
    InterpreterActionBundle,
    InterpreterRoutingDecision,
    to_runtime_action_bundle,
    to_runtime_routing_decision,
)
from runtime.llm.openai_client import OpenAIProvider
from runtime.llm.prompts import build_interpreter_input, build_interpreter_instructions
from runtime.protocols.runtime import (
    ActionBundle,
    ConversationMode,
    ExecutionTrigger,
    ResolverStrategy,
    RoutingDecision,
    RuntimeActionType,
    ScopeOfEffect,
    TargetScope,
)
from runtime.protocols.tasks import (
    ControlCommandType,
    Priority,
    TaskReferenceRelation,
    TaskReferenceType,
)
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
        parsed = self._normalize_interpretation(
            parsed,
            message_id=message_id,
            text=text,
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
        routing_decision = to_runtime_routing_decision(parsed.routing_decision)
        action_bundle = to_runtime_action_bundle(parsed.action_bundle)
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

    def _normalize_interpretation(
        self,
        parsed: InterpretationEnvelope,
        *,
        message_id: str,
        text: str,
    ) -> InterpretationEnvelope:
        lowered = text.lower().strip()
        if self._looks_like_social_or_meta_chat(lowered):
            context_actions = self._context_actions(parsed, text=text)
            return InterpretationEnvelope(
                routing_decision=InterpreterRoutingDecision(
                    decision_id=parsed.routing_decision.decision_id,
                    message_id=message_id,
                    conversation_action_enabled=True,
                    task_action_enabled=False,
                    context_action_enabled=True,
                    conversation_mode=ConversationMode.CONVERSATION_ONLY,
                    needs_clarification=False,
                    clarification_reason="",
                    priority_hint=Priority.NORMAL,
                    resolver_strategy=ResolverStrategy.IMPLICIT,
                    confidence=max(parsed.routing_decision.confidence, 0.6),
                ),
                action_bundle=InterpreterActionBundle(
                    bundle_id=parsed.action_bundle.bundle_id,
                    message_id=message_id,
                    actions=context_actions,
                ),
            )
        if (
            parsed.routing_decision.conversation_mode == ConversationMode.CONVERSATION_ONLY
            and not self._has_task_actions(parsed.action_bundle.actions)
        ):
            return self._normalize_capability_gated_request(
                parsed,
                message_id=message_id,
                text=text,
            )
        return parsed

    def _context_actions(
        self,
        parsed: InterpretationEnvelope,
        *,
        text: str,
    ) -> list[InterpreterAction]:
        context_actions = [
            action
            for action in parsed.action_bundle.actions
            if action.action_type == RuntimeActionType.APPLY_CONTEXT_PATCH
        ]
        if context_actions:
            return context_actions
        return [
            InterpreterAction(
                action_id=new_id("action"),
                action_type=RuntimeActionType.APPLY_CONTEXT_PATCH,
                target_scope=TargetScope.SESSION,
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.NONE,
                scope_of_effect=ScopeOfEffect.SESSION,
                command_type=ControlCommandType.CANCEL_TASK,
                target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                target_task_reference_relation=TaskReferenceRelation.CURRENT,
                latest_user_goal=text,
            )
        ]

    def _normalize_capability_gated_request(
        self,
        parsed: InterpretationEnvelope,
        *,
        message_id: str,
        text: str,
    ) -> InterpretationEnvelope:
        task_action = InterpreterAction(
            action_id=new_id("action"),
            action_type=RuntimeActionType.CREATE_TASK,
            target_scope=TargetScope.NEW_TASK,
            priority=Priority.NORMAL,
            execution_trigger=ExecutionTrigger.HARD,
            scope_of_effect=ScopeOfEffect.TASK,
            title=text[:80],
            goal=text,
            requires_executor_capability=True,
        )
        context_actions = self._context_actions(parsed, text=text)
        return InterpretationEnvelope(
            routing_decision=InterpreterRoutingDecision(
                decision_id=parsed.routing_decision.decision_id,
                message_id=message_id,
                conversation_action_enabled=True,
                task_action_enabled=True,
                context_action_enabled=True,
                conversation_mode=ConversationMode.TASK,
                needs_clarification=False,
                clarification_reason="",
                priority_hint=Priority.NORMAL,
                resolver_strategy=ResolverStrategy.IMPLICIT,
                confidence=max(parsed.routing_decision.confidence, 0.6),
            ),
            action_bundle=InterpreterActionBundle(
                bundle_id=parsed.action_bundle.bundle_id,
                message_id=message_id,
                actions=[task_action, *context_actions],
            ),
        )

    def _has_task_actions(self, actions: list[InterpreterAction]) -> bool:
        return any(
            action.action_type in {
                RuntimeActionType.CREATE_TASK,
                RuntimeActionType.UPDATE_TASK,
                RuntimeActionType.CONTROL_TASK,
            }
            for action in actions
        )

    def _looks_like_social_or_meta_chat(self, text: str) -> bool:
        if not text:
            return False

        chat_patterns = (
            r"^(hi|hello|hey|yo|good morning|good afternoon|good evening)\b",
            r"^(how are you|how's it going|what's up)\b",
            r"^(thanks|thank you|ok|okay|cool|nice)\b",
            r"^(who are you|what are you|what does this system do|what can you do)\b",
            r"^(tell me more about (this|synopse)|explain (this|that|synopse))\b",
        )
        if any(re.search(pattern, text) for pattern in chat_patterns):
            return True
        return False
