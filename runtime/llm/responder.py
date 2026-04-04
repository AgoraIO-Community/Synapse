from __future__ import annotations

from runtime.llm.errors import LLMInvocationError
from runtime.llm.openai_client import OpenAIProvider
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
        return await self._provider.render_text(
            instructions=build_response_instructions(),
            input_text=build_response_input(action),
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )
