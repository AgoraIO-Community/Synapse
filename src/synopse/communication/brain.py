from __future__ import annotations

from synopse.blackboard import BlackboardStore

from .context import CommunicationContextBuilder
from .history import InMemoryConversationHistory
from .model import CommunicationModel
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
    ) -> None:
        self._store = store
        self._model = model
        self._history = history or InMemoryConversationHistory()
        self._tools = tool_registry or build_default_tool_registry(store)
        self._tool_usage_policy = ToolUsagePolicy(self._tools.names)
        self._context_builder = CommunicationContextBuilder(store, self._history)

    async def handle_user_message(
        self,
        conversation_id: str,
        user_text: str,
    ) -> CommunicationTurnResult:
        self._history.append_user(conversation_id, user_text)
        context = await self._context_builder.build(
            conversation_id,
            available_tools=self._tool_usage_policy.available_tools,
        )
        result = await self._model.respond(
            user_text=user_text,
            context=context,
            tool_registry=self._tools,
        )
        assistant_entry = self._history.append_assistant(conversation_id, result.reply_text)
        return CommunicationTurnResult(
            message_id=assistant_entry.message_id,
            reply_text=result.reply_text,
            conversational_act=result.conversational_act or "model_reply",
            tool_invocations=result.tool_invocations,
            affected_task_ids=result.affected_task_ids,
        )
