from __future__ import annotations

from collections.abc import AsyncIterator

from runtime.llm.errors import LLMInvocationError
from runtime.llm.openai_client import OpenAIProvider
from runtime.llm.render_result import LLMResponseDetails, LLMResponseStreamEvent
from runtime.llm.prompts import build_response_input, build_response_instructions
from runtime.protocols.conversation import ConversationAction, ConversationActionType
from runtime.shared_blackboard.trace_state import TraceStateStore


class ResponseClient:
    def __init__(
        self,
        provider: OpenAIProvider | None = None,
    ) -> None:
        self._provider = provider

    async def render(
        self,
        action: ConversationAction,
        *,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> str:
        if action.render_text:
            return action.render_text

        if action.action_type == ConversationActionType.CHAT_REPLY and not action.metadata.get(
            "user_message"
        ):
            raise LLMInvocationError("chat_reply requires metadata.user_message for response generation.")

        if self._provider is None:
            raise LLMInvocationError("Response generator is missing its OpenAI provider.")
        result = await self._provider.render_text_result(
            instructions=build_response_instructions(),
            input_text=build_response_input(action),
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )
        return result.output_text

    async def render_result(
        self,
        action: ConversationAction,
        *,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> tuple[str, LLMResponseDetails | None]:
        if action.render_text:
            return action.render_text, None

        if action.action_type == ConversationActionType.CHAT_REPLY and not action.metadata.get(
            "user_message"
        ):
            raise LLMInvocationError("chat_reply requires metadata.user_message for response generation.")

        if self._provider is None:
            raise LLMInvocationError("Response generator is missing its OpenAI provider.")
        result = await self._provider.render_text_result(
            instructions=build_response_instructions(),
            input_text=build_response_input(action),
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )
        return result.output_text, result

    async def stream_render(
        self,
        action: ConversationAction,
        *,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> AsyncIterator[str]:
        if action.render_text:
            yield action.render_text
            return

        if action.action_type == ConversationActionType.CHAT_REPLY and not action.metadata.get(
            "user_message"
        ):
            raise LLMInvocationError("chat_reply requires metadata.user_message for response generation.")

        if self._provider is None:
            raise LLMInvocationError("Response generator is missing its OpenAI provider.")

        async for event in self._provider.stream_text_result(
            instructions=build_response_instructions(),
            input_text=build_response_input(action),
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        ):
            if event.is_final:
                continue
            yield event.delta

    async def stream_render_result(
        self,
        action: ConversationAction,
        *,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> AsyncIterator[LLMResponseStreamEvent]:
        if action.render_text:
            yield LLMResponseStreamEvent(delta="", is_final=True)
            return

        if action.action_type == ConversationActionType.CHAT_REPLY and not action.metadata.get(
            "user_message"
        ):
            raise LLMInvocationError("chat_reply requires metadata.user_message for response generation.")

        if self._provider is None:
            raise LLMInvocationError("Response generator is missing its OpenAI provider.")

        async for event in self._provider.stream_text_result(
            instructions=build_response_instructions(),
            input_text=build_response_input(action),
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        ):
            yield event
