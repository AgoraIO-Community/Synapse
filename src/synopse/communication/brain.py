from __future__ import annotations

from synopse.blackboard import BlackboardStore

from .context import CommunicationContextBuilder
from .history import InMemoryConversationHistory
from .model import CommunicationModel
from .policies import ToolUsagePolicy, render_reply
from .tools import ToolRegistry, build_default_tool_registry
from .types import CommunicationTurnResult, ToolInvocationRecord


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
        decision = await self._model.decide(user_text=user_text, context=context)

        tool_invocations: list[ToolInvocationRecord] = []
        affected_task_ids: list[str] = []
        tool_results: dict[str, object] = {}
        for call in decision.tool_calls:
            tool = self._tools.get(call.name)
            result = await tool(**call.args)
            tool_results[call.name] = result
            tool_invocations.append(
                ToolInvocationRecord(tool_name=call.name, args=call.args, result=result)
            )
            task_id = _extract_task_id(result)
            if task_id and task_id not in affected_task_ids:
                affected_task_ids.append(task_id)

        reply_text = render_reply(
            decision.conversational_act,
            tool_results=tool_results,
            reply_override=decision.reply_override,
        )
        assistant_entry = self._history.append_assistant(conversation_id, reply_text)
        return CommunicationTurnResult(
            message_id=assistant_entry.message_id,
            reply_text=reply_text,
            conversational_act=decision.conversational_act,
            tool_invocations=tool_invocations,
            affected_task_ids=affected_task_ids,
        )


def _extract_task_id(result: object) -> str | None:
    task_id = getattr(result, "task_id", None)
    if isinstance(task_id, str):
        return task_id
    if isinstance(result, dict):
        task = result.get("task")
        task_id = getattr(task, "task_id", None)
        if isinstance(task_id, str):
            return task_id
    return None
