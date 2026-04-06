from __future__ import annotations

from synopse.communication.history import ConversationEntry
from synopse.blackboard import BlackboardStore
from synopse.executor_core import ExecutorCapabilities

from .context import CommunicationContextBuilder
from .history import InMemoryConversationHistory
from .model import CommunicationModel, TextDeltaCallback
from .policies import ToolUsagePolicy
from .tools import ToolRegistry, build_default_tool_registry
from .types import CommunicationTurnResult


class CommunicationBrain:
    def __init__(
        self,
        store: BlackboardStore,
        model: CommunicationModel,
        *,
        history: InMemoryConversationHistory | None = None,
        tool_registry: ToolRegistry | None = None,
        executor_capabilities: list[ExecutorCapabilities] | None = None,
        default_executor_type: str | None = None,
    ) -> None:
        self._store = store
        self._model = model
        self._history = history or InMemoryConversationHistory()
        self._tools = tool_registry or build_default_tool_registry(store)
        self._tool_usage_policy = ToolUsagePolicy(self._tools.names)
        self._context_builder = CommunicationContextBuilder(
            store,
            self._history,
            executor_capabilities=executor_capabilities,
            default_executor_type=default_executor_type,
        )

    async def handle_user_message(
        self,
        conversation_id: str,
        user_text: str,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> CommunicationTurnResult:
        self.append_user_message(conversation_id, user_text)
        return await self.generate_reply(
            conversation_id,
            user_text,
            on_text_delta=on_text_delta,
        )

    def append_user_message(self, conversation_id: str, user_text: str) -> ConversationEntry:
        return self._history.append_user(conversation_id, user_text)

    async def generate_reply(
        self,
        conversation_id: str,
        user_text: str,
        *,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> CommunicationTurnResult:
        context = await self._context_builder.build(
            conversation_id,
            available_tools=self._tool_usage_policy.available_tools,
        )
        respond_kwargs = {
            "user_text": user_text,
            "context": context,
            "tool_registry": self._tools,
        }
        if on_text_delta is not None:
            respond_kwargs["on_text_delta"] = on_text_delta
        result = await self._model.respond(**respond_kwargs)
        assistant_entry = self._history.append_assistant(conversation_id, result.reply_text)
        return CommunicationTurnResult(
            message_id=assistant_entry.message_id,
            reply_text=result.reply_text,
            conversational_act=result.conversational_act or "model_reply",
            tool_invocations=result.tool_invocations,
            affected_task_ids=result.affected_task_ids,
        )
