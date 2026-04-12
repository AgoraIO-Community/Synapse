from __future__ import annotations

from synapse.communication.history import ConversationEntry
from synapse.blackboard import BlackboardStore
from synapse.observability.emitters import CommunicationDiagnosticEmitter
from synapse.protocol import NotificationCandidate
from synapse.executor_core import ExecutorCapabilities

from .context import CommunicationContextBuilder
from .history import InMemoryConversationHistory
from .model import CommunicationModel, LlmTraceCallback, TextDeltaCallback, ToolCallCallback
from .policies import ToolUsagePolicy
from .prompts.runtime_context import build_notification_rendering_context
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
        trace_callback: LlmTraceCallback | None = None,
        observability: CommunicationDiagnosticEmitter | None = None,
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
        self._trace_callback = trace_callback
        self._observability = observability

    def set_trace_callback(self, callback: LlmTraceCallback | None) -> None:
        self._trace_callback = callback

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
        on_trace: LlmTraceCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> CommunicationTurnResult:
        if self._observability is not None:
            self._observability.message_received(
                conversation_id=conversation_id,
                user_text=user_text,
            )
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
        if on_trace is not None:
            respond_kwargs["on_trace"] = on_trace
        elif self._trace_callback is not None:
            respond_kwargs["on_trace"] = self._trace_callback
        if on_tool_call is not None:
            respond_kwargs["on_tool_call"] = on_tool_call
        result = await self._model.respond(**respond_kwargs)
        assistant_entry = self._history.append_assistant(conversation_id, result.reply_text)
        if self._observability is not None:
            self._observability.reply_generated(
                conversation_id=conversation_id,
                request_id=None,
                conversational_act=result.conversational_act or "model_reply",
                affected_task_ids=result.affected_task_ids,
                reply_text=result.reply_text,
            )
        return CommunicationTurnResult(
            message_id=assistant_entry.message_id,
            reply_text=result.reply_text,
            conversational_act=result.conversational_act or "model_reply",
            tool_invocations=result.tool_invocations,
            affected_task_ids=result.affected_task_ids,
        )

    async def emit_notification(
        self,
        conversation_id: str,
        *,
        candidates: list[NotificationCandidate],
        on_trace: LlmTraceCallback | None = None,
        on_tool_call: ToolCallCallback | None = None,
    ) -> CommunicationTurnResult:
        context = await self._context_builder.build(
            conversation_id,
            available_tools=self._tool_usage_policy.available_tools,
        )
        rendering_context = build_notification_rendering_context(context, candidates)
        key_task = rendering_context.get("key_task")
        relevant_tasks = rendering_context.get("relevant_tasks", [])
        try:
            reply_text = await self._model.render_notification(
                context=context,
                candidates=candidates,
                on_trace=on_trace or self._trace_callback,
                on_tool_call=on_tool_call,
            )
        except Exception:
            if len(candidates) == 1:
                reply_text = candidates[0].summary_short
            else:
                reply_text = "; ".join(candidate.summary_short for candidate in candidates)
        assistant_entry = self._history.append_assistant(conversation_id, reply_text)
        if self._observability is not None:
            self._observability.reply_generated(
                conversation_id=conversation_id,
                request_id=None,
                conversational_act="inform_progress",
                affected_task_ids=sorted({candidate.task_id for candidate in candidates}),
                reply_text=reply_text,
            )
        return CommunicationTurnResult(
            message_id=assistant_entry.message_id,
            reply_text=reply_text,
            conversational_act="inform_progress",
            affected_task_ids=sorted({candidate.task_id for candidate in candidates}),
            notification_key_task_id=(
                str(key_task.get("task_id")) if isinstance(key_task, dict) and key_task.get("task_id") else None
            ),
            notification_relevant_task_ids=[
                str(task.get("task_id"))
                for task in relevant_tasks
                if isinstance(task, dict) and task.get("task_id")
            ],
        )
