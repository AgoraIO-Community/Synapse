from __future__ import annotations

from runtime.communication_brain.dialog_manager import DialogManager
from runtime.communication_brain.response_generator import ResponseGenerator
from runtime.executors.registry import ExecutorRegistry
from runtime.execution_brain.event_normalizer import apply_execution_event_to_task
from runtime.execution_brain.executor_router import ExecutorRouter
from runtime.execution_brain.task_graph import build_task
from runtime.infrastructure.ids import new_id
from runtime.infrastructure.time import utc_now
from runtime.message_router.priorities import sort_actions
from runtime.message_router.resolver import resolve_task_reference
from runtime.protocols.conversation import ConversationAction, ConversationActionType
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.runtime import ActionBundle, ContextPatch, RuntimeActionType
from runtime.protocols.stream import StreamCategory
from runtime.protocols.tasks import ControlCommand, ControlCommandType, TaskStatus
from runtime.shared_blackboard.mutations import (
    apply_context_patch,
    apply_control,
    apply_task_update,
    upsert_task,
)
from runtime.shared_blackboard.store import SharedBlackboardStore


class ExecutionOrchestrator:
    def __init__(
        self,
        store: SharedBlackboardStore,
        registry: ExecutorRegistry,
        executor_router: ExecutorRouter,
        dialog_manager: DialogManager,
        response_generator: ResponseGenerator,
    ) -> None:
        self._store = store
        self._registry = registry
        self._executor_router = executor_router
        self._dialog_manager = dialog_manager
        self._response_generator = response_generator

    async def process_bundle(self, session_id: str, bundle: ActionBundle) -> None:
        session = self._store.get_session(session_id)
        for action in sort_actions(bundle.actions):
            if action.action_type == RuntimeActionType.APPLY_CONTEXT_PATCH:
                patch = ContextPatch.model_validate(action.payload)
                apply_context_patch(session, patch)
                await self._store.publish(
                    session_id,
                    StreamCategory.CONTEXT,
                    "context_patch_applied",
                    "message_router",
                    patch.model_dump(mode="json"),
                    related_message_id=bundle.message_id,
                )
            elif action.action_type == RuntimeActionType.CREATE_TASK:
                task = build_task(
                    action,
                    message_id=bundle.message_id,
                    executor_id=self._executor_router.default_executor_id,
                )
                upsert_task(session, task)
                await self._store.publish(
                    session_id,
                    StreamCategory.TASK,
                    "task_created",
                    "execution_brain",
                    task.model_dump(mode="json"),
                    related_task_id=task.task_id,
                    related_message_id=bundle.message_id,
                )
                await self._start_task(session_id, task)
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
                if task.status == TaskStatus.BLOCKED:
                    task.input_context["clarification_received"] = True
                await self._store.publish(
                    session_id,
                    StreamCategory.TASK,
                    "task_updated",
                    "execution_brain",
                    task.model_dump(mode="json"),
                    related_task_id=task.task_id,
                    related_message_id=bundle.message_id,
                )
                if task.status in {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.PAUSED}:
                    await self._resume_task(session_id, task)
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
                await self.apply_control_command(session_id, command)

    async def apply_control_command(
        self, session_id: str, command: ControlCommand
    ) -> None:
        session = self._store.get_session(session_id)
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

        apply_control(task, command.command_type)
        executor_id = self._executor_router.select_executor_id(task)
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

        await self._store.publish(
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
        session = self._store.get_session(session_id)
        task = session.task_registry[event.task_id]
        apply_execution_event_to_task(task, event)
        task.updated_at = utc_now()
        await self._store.publish(
            session_id,
            StreamCategory.EXECUTION,
            event.event_type.value,
            event.source,
            event.model_dump(mode="json"),
            related_task_id=event.task_id,
        )
        conv_action = self._dialog_manager.on_execution_event(session_id, event)
        if conv_action:
            await self.emit_conversation_action(session_id, conv_action, related_task_id=event.task_id)

    async def emit_conversation_action(
        self,
        session_id: str,
        action: ConversationAction,
        *,
        related_task_id: str | None = None,
        related_message_id: str | None = None,
    ) -> None:
        action = self._response_generator.finalize(action)
        event = self._dialog_manager.to_event(session_id, action)
        if action.action_type == ConversationActionType.CLARIFY:
            self._store.add_pending_clarification(session_id, action)
        await self._store.publish(
            session_id,
            StreamCategory.COMMUNICATION,
            action.action_type.value,
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

    async def _start_task(self, session_id: str, task) -> None:
        executor_id = self._executor_router.select_executor_id(task)
        task.assigned_executor = executor_id
        executor = self._registry.get(executor_id)
        await executor.start_task(
            task,
            lambda event: self.handle_execution_event(session_id, event),
            session_id=session_id,
        )

    async def _resume_task(self, session_id: str, task) -> None:
        executor_id = self._executor_router.select_executor_id(task)
        executor = self._registry.get(executor_id)
        await executor.resume_task(
            task,
            lambda event: self.handle_execution_event(session_id, event),
            session_id=session_id,
        )
