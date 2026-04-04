from __future__ import annotations

from runtime.llm.errors import LLMInvocationError
from runtime.llm.openai_client import OpenAIProvider
from runtime.llm.prompts import build_response_input, build_response_instructions
from runtime.protocols.conversation import ConversationAction


class ResponseClient:
    def __init__(
        self,
        provider: OpenAIProvider | None = None,
    ) -> None:
        self._provider = provider

    def render(self, action: ConversationAction) -> str:
        if action.render_text:
            return action.render_text

        if self._provider is None:
            raise LLMInvocationError("Response generator is missing its OpenAI provider.")
        return self._provider.render_text(
            instructions=build_response_instructions(),
            input_text=build_response_input(action),
        )
