from __future__ import annotations

from runtime.communication_brain.event_to_response import EventToResponseMapper
from runtime.executors.bootstrap import MOCK_EXECUTOR_ID
from runtime.executors.errors import UnsupportedExecutorCommandError
from runtime.communication_brain.response_generator import ResponseGenerator
from runtime.executors.registry import ExecutorRegistry
from runtime.execution_brain.executor_adapter_router import ExecutorAdapterRouter
from runtime.execution_brain.event_normalizer import apply_execution_event_to_task
from runtime.execution_brain.task_graph import build_task
from runtime.infrastructure.ids import new_id
from runtime.infrastructure.time import utc_now
from runtime.llm.errors import LLMConfigurationError, LLMInvocationError
from runtime.action_router.priorities import sort_actions
from runtime.action_router.resolver import resolve_task_reference
from runtime.protocols.conversation import (
    CommunicationChunkEvent,
    ConversationAction,
    ConversationActionType,
)
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.runtime import ActionBundle, ContextPatch, RuntimeActionType
from runtime.protocols.stream import StreamCategory
from runtime.protocols.trace import TraceStage
from runtime.protocols.tasks import ControlCommand, ControlCommandType, TaskStatus
from runtime.shared_blackboard.mutations import (
    apply_context_patch,
    apply_control,
    apply_task_update,
    upsert_task,
)
from runtime.shared_blackboard.runtime_state import RuntimeStateStore
from runtime.shared_blackboard.trace_state import TraceStateStore


class ExecutionOrchestrator:
    def __init__(
        self,
        runtime_state_store: RuntimeStateStore,
        trace_state_store: TraceStateStore,
        registry: ExecutorRegistry,
        executor_adapter_router: ExecutorAdapterRouter,
        event_to_response_mapper: EventToResponseMapper,
        response_generator: ResponseGenerator,
    ) -> None:
        self._runtime_state_store = runtime_state_store
        self._trace_state_store = trace_state_store
        self._registry = registry
        self._executor_adapter_router = executor_adapter_router
        self._event_to_response_mapper = event_to_response_mapper
        self._response_generator = response_generator

    async def process_bundle(
        self,
        session_id: str,
        bundle: ActionBundle,
        *,
        span_id: str | None = None,
    ) -> None:
        session = self._runtime_state_store.get_session(session_id)
        await self._trace_state_store.publish(
            session_id,
            TraceStage.EXECUTION_ORCHESTRATOR,
            "bundle_processing_started",
            "execution_orchestrator",
            {"action_count": len(bundle.actions)},
            span_id=span_id,
            related_message_id=bundle.message_id,
        )
        for action in sort_actions(bundle.actions):
            if action.action_type == RuntimeActionType.APPLY_CONTEXT_PATCH:
                patch = ContextPatch.model_validate(action.payload)
                apply_context_patch(session, patch)
                await self._trace_state_store.publish(
                    session_id,
                    TraceStage.RUNTIME_STATE,
                    "context_patch_applied",
                    "runtime_state",
                    {"action_type": action.action_type.value},
                    span_id=span_id,
                    related_message_id=bundle.message_id,
                )
                await self._runtime_state_store.publish(
                    session_id,
                    StreamCategory.CONTEXT,
                    "context_patch_applied",
                    "action_router",
                    patch.model_dump(mode="json"),
                    related_message_id=bundle.message_id,
                )
            elif action.action_type == RuntimeActionType.CREATE_TASK:
                task = build_task(
                    action,
                    message_id=bundle.message_id,
                    executor_id=self._executor_adapter_router.default_executor_id,
                )
                if self._requires_real_executor(task):
                    await self._emit_executor_unavailable(
                        session_id,
                        message_id=bundle.message_id,
                    )
                    await self._trace_state_store.publish(
                        session_id,
                        TraceStage.EXECUTION_ORCHESTRATOR,
                        "task_skipped_real_executor_unavailable",
                        "execution_orchestrator",
                        {"goal": task.goal},
                        span_id=span_id,
                        related_message_id=bundle.message_id,
                    )
                    continue
                await self._trace_state_store.publish(
                    session_id,
                    TraceStage.TASK_GRAPH,
                    "task_built",
                    "task_graph",
                    {"title": task.title, "goal": task.goal},
                    span_id=span_id,
                    related_message_id=bundle.message_id,
                    related_task_id=task.task_id,
                )
                upsert_task(session, task)
                await self._runtime_state_store.publish(
                    session_id,
                    StreamCategory.TASK,
                    "task_created",
                    "execution_brain",
                    task.model_dump(mode="json"),
                    related_task_id=task.task_id,
                    related_message_id=bundle.message_id,
                )
                await self._start_task(session_id, task, span_id=span_id)
            elif action.action_type == RuntimeActionType.UPDATE_TASK:
                task = resolve_task_reference(session, action.target_task_ref)
                if task is None:
                    await self._emit_clarification(
                        session_id,
                        reason="I could not identify which task to update.",
                        message_id=bundle.message_id,
                    )
                    continue
                apply_task_update(task, action.payload)
                await self._trace_state_store.publish(
                    session_id,
                    TraceStage.EXECUTION_ORCHESTRATOR,
                    "task_updated_from_action",
                    "execution_orchestrator",
                    {"latest_instruction": action.payload.get("latest_instruction")},
                    span_id=span_id,
                    related_message_id=bundle.message_id,
                    related_task_id=task.task_id,
                )
                if task.status == TaskStatus.BLOCKED:
                    task.input_context["clarification_received"] = True
                await self._runtime_state_store.publish(
                    session_id,
                    StreamCategory.TASK,
                    "task_updated",
                    "execution_brain",
                    task.model_dump(mode="json"),
                    related_task_id=task.task_id,
                    related_message_id=bundle.message_id,
                )
                if task.status in {
                    TaskStatus.RUNNING,
                    TaskStatus.BLOCKED,
                    TaskStatus.PAUSED,
                } and self._supports_command(task, ControlCommandType.RESUME_TASK):
                    await self._resume_task(session_id, task, span_id=span_id)
            elif action.action_type == RuntimeActionType.CONTROL_TASK:
                task = resolve_task_reference(session, action.target_task_ref)
                if task is None:
                    await self._emit_clarification(
                        session_id,
                        reason="I could not identify which task to control.",
                        message_id=bundle.message_id,
                    )
                    continue
                command_type = ControlCommandType(action.payload["command_type"])
                command = ControlCommand(
                    command_id=new_id("cmd"),
                    target_task_ref=action.target_task_ref,
                    target_task_id=task.task_id,
                    command_type=command_type,
                    reason=action.payload.get("reason"),
                )
                try:
                    await self.apply_control_command(session_id, command)
                except UnsupportedExecutorCommandError as exc:
                    await self._emit_unsupported_command(
                        session_id,
                        executor_id=exc.executor_id,
                        command_type=exc.command_type,
                        message_id=bundle.message_id,
                    )
        await self._trace_state_store.publish(
            session_id,
            TraceStage.EXECUTION_ORCHESTRATOR,
            "bundle_processing_completed",
            "execution_orchestrator",
            {"action_count": len(bundle.actions)},
            span_id=span_id,
            related_message_id=bundle.message_id,
        )

    async def apply_control_command(
        self, session_id: str, command: ControlCommand
    ) -> None:
        session = self._runtime_state_store.get_session(session_id)
        task = session.task_registry.get(command.target_task_id or "")
        if task is None:
            task = resolve_task_reference(session, command.target_task_ref)
        if task is None:
            await self._emit_clarification(
                session_id,
                reason="No matching task exists for that command.",
                message_id=None,
            )
            return

        executor_id = self._executor_adapter_router.select_executor_id(task)
        self._ensure_command_supported(executor_id, command.command_type)
        apply_control(task, command.command_type)
        executor = self._registry.get(executor_id)
        if command.command_type == ControlCommandType.PAUSE_TASK:
            await executor.pause_task(task.task_id)
        elif command.command_type == ControlCommandType.RESUME_TASK:
            task.input_context["clarification_received"] = True
            await executor.resume_task(
                task,
                lambda event: self.handle_execution_event(session_id, event),
                session_id=session_id,
            )
        elif command.command_type == ControlCommandType.CANCEL_TASK:
            await executor.cancel_task(task.task_id)
            await self.handle_execution_event(
                session_id,
                ExecutionEvent(
                    event_id=new_id("exec"),
                    task_id=task.task_id,
                    executor_id=executor_id,
                    event_type=ExecutionEventType.CANCELED,
                    status=TaskStatus.CANCELED,
                    progress_message="Task canceled.",
                ),
            )
            return
        elif command.command_type == ControlCommandType.RETRY_TASK:
            await self._start_task(session_id, task)

        await self._runtime_state_store.publish(
            session_id,
            StreamCategory.TASK,
            command.command_type.value,
            "execution_brain",
            task.model_dump(mode="json"),
            related_task_id=task.task_id,
        )

    async def handle_execution_event(
        self, session_id: str, event: ExecutionEvent
    ) -> None:
        session = self._runtime_state_store.get_session(session_id)
        await self._trace_state_store.publish(
            session_id,
            TraceStage.EXECUTION_ORCHESTRATOR,
            "execution_event_received",
            "execution_orchestrator",
            {"event_type": event.event_type.value, "status": event.status.value},
            related_task_id=event.task_id,
        )
        task = session.task_registry[event.task_id]
        apply_execution_event_to_task(task, event)
        task.updated_at = utc_now()
        await self._runtime_state_store.publish(
            session_id,
            StreamCategory.EXECUTION,
            event.event_type.value,
            event.source,
            event.model_dump(mode="json"),
            related_task_id=event.task_id,
        )
        conv_action = self._event_to_response_mapper.on_execution_event(session_id, event)
        if conv_action:
            await self._trace_state_store.publish(
                session_id,
                TraceStage.RESPONSE_GENERATOR,
                "response_mapping_completed",
                "event_to_response",
                {"action_type": conv_action.action_type.value},
                related_task_id=event.task_id,
            )
            await self.emit_conversation_action(session_id, conv_action, related_task_id=event.task_id)

    async def emit_conversation_action(
        self,
        session_id: str,
        action: ConversationAction,
        *,
        related_task_id: str | None = None,
        related_message_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        await self._trace_state_store.publish(
            session_id,
            TraceStage.RESPONSE_GENERATOR,
            "response_render_started",
            "response_generator",
            {"action_type": action.action_type.value},
            span_id=span_id,
            related_task_id=related_task_id or action.target_task_id,
            related_message_id=related_message_id,
        )
        try:
            if action.render_text:
                action = await self._response_generator.finalize(
                    action,
                    trace_state_store=self._trace_state_store,
                    session_id=session_id,
                    span_id=span_id,
                    related_message_id=related_message_id,
                    related_task_id=related_task_id or action.target_task_id,
                )
            else:
                async for chunk in self._response_generator.stream_finalize(
                    action,
                    trace_state_store=self._trace_state_store,
                    session_id=session_id,
                    span_id=span_id,
                    related_message_id=related_message_id,
                    related_task_id=related_task_id or action.target_task_id,
                ):
                    if chunk.is_final:
                        action.render_text = chunk.text
                    elif chunk.delta:
                        await self._publish_response_chunk(
                            session_id,
                            action,
                            render_text_delta=chunk.delta,
                            render_text=chunk.text,
                            related_task_id=related_task_id or action.target_task_id,
                            related_message_id=related_message_id,
                        )
        except (LLMConfigurationError, LLMInvocationError) as exc:
            await self._trace_state_store.publish(
                session_id,
                TraceStage.RESPONSE_GENERATOR,
                "response_render_failed",
                "response_generator",
                {"error": str(exc), "action_type": action.action_type.value},
                span_id=span_id,
                related_task_id=related_task_id or action.target_task_id,
                related_message_id=related_message_id,
            )
            await self._runtime_state_store.publish(
                session_id,
                StreamCategory.SYSTEM,
                "communication_render_failed",
                "communication_brain",
                {
                    "error": str(exc),
                    "action_type": action.action_type.value,
                },
                related_task_id=related_task_id or action.target_task_id,
                related_message_id=related_message_id,
            )
            if related_message_id is not None:
                raise
            return
        await self._trace_state_store.publish(
            session_id,
            TraceStage.RESPONSE_GENERATOR,
            "response_render_completed",
            "response_generator",
            {"action_type": action.action_type.value},
            span_id=span_id,
            related_task_id=related_task_id or action.target_task_id,
            related_message_id=related_message_id,
        )
        event = self._event_to_response_mapper.to_event(session_id, action)
        if action.action_type == ConversationActionType.CLARIFY:
            self._runtime_state_store.add_pending_clarification(session_id, action)
        await self._runtime_state_store.publish(
            session_id,
            StreamCategory.COMMUNICATION,
            action.action_type.value,
            event.source,
            event.model_dump(mode="json"),
            related_task_id=related_task_id or action.target_task_id,
            related_message_id=related_message_id,
        )

    async def _publish_response_chunk(
        self,
        session_id: str,
        action: ConversationAction,
        *,
        render_text_delta: str,
        render_text: str,
        related_task_id: str | None = None,
        related_message_id: str | None = None,
    ) -> None:
        event = CommunicationChunkEvent(
            event_id=new_id("comm_chunk"),
            session_id=session_id,
            action_id=action.action_id,
            action_type=action.action_type,
            target_task_id=related_task_id or action.target_task_id,
            render_text_delta=render_text_delta,
            render_text=render_text,
        )
        await self._runtime_state_store.publish_transient(
            session_id,
            StreamCategory.COMMUNICATION,
            "response_chunk",
            event.source,
            event.model_dump(mode="json"),
            related_task_id=related_task_id or action.target_task_id,
            related_message_id=related_message_id,
        )

    async def _emit_clarification(
        self, session_id: str, *, reason: str, message_id: str | None
    ) -> None:
        action = ConversationAction(
            action_id=new_id("conv"),
            action_type=ConversationActionType.CLARIFY,
            reason=reason,
        )
        await self.emit_conversation_action(
            session_id,
            action,
            related_message_id=message_id,
        )

    async def _emit_executor_unavailable(
        self, session_id: str, *, message_id: str | None
    ) -> None:
        action = ConversationAction(
            action_id=new_id("conv"),
            action_type=ConversationActionType.CHAT_REPLY,
            reason="A real executor is required for that request, but Codex is not enabled in this runtime.",
            render_text=(
                "I can't check that right now because this runtime is still using the mock executor. "
                "Enable Codex to handle system or external lookup requests."
            ),
        )
        await self.emit_conversation_action(
            session_id,
            action,
            related_message_id=message_id,
        )

    async def _emit_unsupported_command(
        self,
        session_id: str,
        *,
        executor_id: str,
        command_type: str,
        message_id: str | None,
    ) -> None:
        capability = self._registry.get_capability(executor_id)
        verb = command_type.replace("_task", "").replace("_", " ")
        action = ConversationAction(
            action_id=new_id("conv"),
            action_type=ConversationActionType.CHAT_REPLY,
            metadata={
                "executor_id": executor_id,
                "executor_label": capability.label,
                "unsupported_command": command_type,
            },
            render_text=(
                f"I can't {verb} that task because it is running on {capability.label}, "
                "and that executor does not support it."
            ),
        )
        await self.emit_conversation_action(
            session_id,
            action,
            related_message_id=message_id,
        )

    def _requires_real_executor(self, task) -> bool:
        if not task.input_context.get("requires_executor_capability"):
            return False
        executor_id = self._executor_adapter_router.select_executor_id(task)
        return executor_id == MOCK_EXECUTOR_ID

    def _supports_command(self, task, command_type: ControlCommandType) -> bool:
        executor_id = self._executor_adapter_router.select_executor_id(task)
        capability = self._registry.get_capability(executor_id)
        if command_type == ControlCommandType.CANCEL_TASK:
            return capability.supports_cancel
        if command_type in {
            ControlCommandType.PAUSE_TASK,
            ControlCommandType.RESUME_TASK,
        }:
            return capability.supports_pause
        return True

    def _ensure_command_supported(
        self, executor_id: str, command_type: ControlCommandType
    ) -> None:
        capability = self._registry.get_capability(executor_id)
        if command_type == ControlCommandType.CANCEL_TASK and capability.supports_cancel:
            return
        if (
            command_type in {ControlCommandType.PAUSE_TASK, ControlCommandType.RESUME_TASK}
            and capability.supports_pause
        ):
            return
        if command_type == ControlCommandType.RETRY_TASK:
            return
        raise UnsupportedExecutorCommandError(
            executor_id=executor_id, command_type=command_type.value
        )

    async def _start_task(self, session_id: str, task, *, span_id: str | None = None) -> None:
        executor_id = self._executor_adapter_router.select_executor_id(task)
        task.assigned_executor = executor_id
        await self._trace_state_store.publish(
            session_id,
            TraceStage.EXECUTOR_ADAPTER,
            "executor_dispatch_started",
            "executor_adapter_router",
            {"executor_id": executor_id},
            span_id=span_id,
            related_task_id=task.task_id,
        )
        executor = self._registry.get(executor_id)
        await executor.start_task(
            task,
            lambda event: self.handle_execution_event(session_id, event),
            session_id=session_id,
        )
        await self._trace_state_store.publish(
            session_id,
            TraceStage.EXECUTOR_ADAPTER,
            "executor_dispatch_completed",
            "executor_adapter_router",
            {"executor_id": executor_id},
            span_id=span_id,
            related_task_id=task.task_id,
        )

    async def _resume_task(self, session_id: str, task, *, span_id: str | None = None) -> None:
        executor_id = self._executor_adapter_router.select_executor_id(task)
        await self._trace_state_store.publish(
            session_id,
            TraceStage.EXECUTOR_ADAPTER,
            "executor_resume_started",
            "executor_adapter_router",
            {"executor_id": executor_id},
            span_id=span_id,
            related_task_id=task.task_id,
        )
        executor = self._registry.get(executor_id)
        await executor.resume_task(
            task,
            lambda event: self.handle_execution_event(session_id, event),
            session_id=session_id,
        )
        await self._trace_state_store.publish(
            session_id,
            TraceStage.EXECUTOR_ADAPTER,
            "executor_resume_completed",
            "executor_adapter_router",
            {"executor_id": executor_id},
            span_id=span_id,
            related_task_id=task.task_id,
        )
