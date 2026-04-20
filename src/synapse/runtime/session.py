from __future__ import annotations

import asyncio
from dataclasses import replace
from dataclasses import dataclass, field

from synapse.blackboard import InMemoryBlackboard
from synapse.communication import CommunicationBrain
from synapse.communication.persona_pool import load_personas_from_file
from synapse.communication.history import InMemoryConversationHistory
from synapse.communication.model import CommunicationModel, LlmTraceRecord, ToolCallRecord
from synapse.communication.tools import build_default_tool_registry
from synapse.communication.types import CommunicationTurnResult
from synapse.executor_adapters.acpx import AcpxExecutor
from synapse.execution import ExecutionBrain
from synapse.executor_adapters.codex import CodexExecutor
from synapse.executor_adapters.mock import MockExecutor
from synapse.executor_core import ExecutorRegistry, UnknownExecutorError
from synapse.notification import NotificationManager
from synapse.observability.bootstrap import SessionObservability, build_session_observability
from synapse.observability.context import bind_diagnostic_context
from synapse.observability.reason_codes import COMMUNICATION_MODEL_FAILURE
from synapse.protocol import (
    BindingStatus,
    ExecutionRun,
    ExecutionSession,
    NotificationDeliveryStatus,
    RunStatus,
    TaskCommand,
    TaskCommandType,
    TaskStatus,
    TaskSummary,
)

from .config import Settings
from .models import (
    ActionAcceptedStreamEvent,
    ActionRejectedStreamEvent,
    AssistantResponseCompletedStreamEvent,
    AssistantResponseDeltaStreamEvent,
    AssistantResponseFailedStreamEvent,
    AssistantResponseStartedStreamEvent,
    ConversationAppendedStreamEvent,
    ConversationHistoryEntryModel,
    ConversationSnapshot,
    SessionSnapshot,
    SessionStreamEventBase,
    SnapshotStreamEvent,
)


FALLBACK_ASSISTANT_ERROR_MESSAGE = "Sorry, something went wrong while generating the reply."


@dataclass(slots=True)
class PendingMessageRequest:
    request_id: str
    user_text: str
    completion: asyncio.Future[CommunicationTurnResult]


@dataclass(slots=True)
class SessionRuntime:
    session_id: str
    blackboard: InMemoryBlackboard
    history: InMemoryConversationHistory
    registry: ExecutorRegistry
    communication_brain: CommunicationBrain
    execution_brain: ExecutionBrain
    notification_manager: NotificationManager
    observability: SessionObservability
    subscribers: list[asyncio.Queue[SessionStreamEventBase]] = field(default_factory=list)
    _message_queue: asyncio.Queue[PendingMessageRequest] = field(default_factory=asyncio.Queue)
    _execution_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _communication_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _notification_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _snapshot_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _diagnostic_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _blackboard_queue: asyncio.Queue | None = field(default=None, init=False, repr=False)
    _notification_blackboard_queue: asyncio.Queue | None = field(default=None, init=False, repr=False)
    _diagnostic_blackboard_queue: asyncio.Queue | None = field(default=None, init=False, repr=False)
    _notification_wakeup: asyncio.Event = field(default_factory=asyncio.Event)
    _next_sequence: int = field(default=1, init=False, repr=False)
    _active_assistant_turns: int = field(default=0, init=False, repr=False)
    _diagnostic_seen_entities: set[tuple[str, str | None]] = field(default_factory=set, init=False, repr=False)

    async def snapshot(self) -> SessionSnapshot:
        tasks = await self.blackboard.list_tasks()
        sessions = await self.blackboard.list_sessions()
        runs = await self.blackboard.list_runs()
        execution_modes = await self.blackboard.list_execution_modes()
        notification_candidates = await self.blackboard.list_notification_candidates()
        bindings = await self.blackboard.list_bindings()
        summaries = [
            summary
            for summary in [await self.blackboard.get_summary(task.task_id) for task in tasks]
            if summary is not None
        ]
        return SessionSnapshot(
            session_id=self.session_id,
            tasks=tasks,
            execution_sessions=sessions,
            execution_runs=runs,
            execution_modes=execution_modes,
            bindings=bindings,
            summaries=summaries,
            notification_candidates=notification_candidates,
            personas=await self.blackboard.list_personas(),
        )

    async def conversation_snapshot(self) -> ConversationSnapshot:
        history = [
            ConversationHistoryEntryModel(
                role=entry.role,
                text=entry.text,
                message_id=entry.message_id,
            )
            for entry in self.history.get_recent(self.session_id, limit=50)
        ]
        return ConversationSnapshot(
            session_id=self.session_id,
            conversation_history=history,
        )

    def diagnostic_timeline(
        self,
        *,
        after_sequence: int | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        execution_session_id: str | None = None,
        notification_id: str | None = None,
        request_id: str | None = None,
        event_prefix: str | None = None,
        min_level: str | None = None,
        limit: int = 200,
    ):
        return self.observability.store.query(
            after_sequence=after_sequence,
            task_id=task_id,
            run_id=run_id,
            execution_session_id=execution_session_id,
            notification_id=notification_id,
            request_id=request_id,
            event_prefix=event_prefix,
            min_level=min_level,
            limit=limit,
        )

    def subscribe(self) -> asyncio.Queue[SessionStreamEventBase]:
        queue: asyncio.Queue[SessionStreamEventBase] = asyncio.Queue()
        self.subscribers.append(queue)
        self._ensure_snapshot_pump()
        return queue

    def unsubscribe(self, queue: asyncio.Queue[SessionStreamEventBase]) -> None:
        if queue in self.subscribers:
            self.subscribers.remove(queue)
        if not self.subscribers and self._snapshot_task is not None:
            self._snapshot_task.cancel()

    async def publish_snapshot(self) -> SessionSnapshot:
        snapshot = await self.snapshot()
        await self._broadcast_event(self._snapshot_event(snapshot))
        return snapshot

    async def initial_snapshot_event(self) -> SnapshotStreamEvent:
        return self._snapshot_event(await self.snapshot())

    async def publish_private_event(
        self,
        queue: asyncio.Queue[SessionStreamEventBase],
        event: SessionStreamEventBase,
    ) -> None:
        await queue.put(event)

    async def submit_message(
        self,
        request_id: str,
        user_text: str,
        *,
        start_processing: bool = True,
    ) -> tuple[str, asyncio.Future[CommunicationTurnResult]]:
        user_entry = self.communication_brain.append_user_message(self.session_id, user_text)
        completion = asyncio.get_running_loop().create_future()
        await self._message_queue.put(
            PendingMessageRequest(
                request_id=request_id,
                user_text=user_text,
                completion=completion,
            )
        )
        self._wake_notification_pump()
        if start_processing:
            self._ensure_communication_pump()
        return user_entry.message_id, completion

    def start_message_processing(self) -> None:
        self._ensure_communication_pump()

    def start_notification_processing(self) -> None:
        self._ensure_notification_pump()

    def action_accepted_event(
        self,
        request_id: str,
        *,
        action_type: str,
    ) -> ActionAcceptedStreamEvent:
        return ActionAcceptedStreamEvent(
            sequence=self._next_event_sequence(),
            request_id=request_id,
            action_type=action_type,
        )

    def action_rejected_event(
        self,
        request_id: str,
        *,
        action_type: str,
        error_code: str,
        message: str,
    ) -> ActionRejectedStreamEvent:
        return ActionRejectedStreamEvent(
            sequence=self._next_event_sequence(),
            request_id=request_id,
            action_type=action_type,
            error_code=error_code,
            message=message,
        )

    def schedule_execution(self) -> None:
        # Always spawn a new execution loop for pending runnable tasks.
        # Old loops that are blocked on a running executor will finish
        # on their own; the reconcile loop's claim mechanism prevents
        # double-execution of the same task.
        self._execution_task = asyncio.create_task(self._run_execution_loop())

    async def apply_command(self, command: TaskCommand) -> list[str]:
        await self.blackboard.append_command(command)
        task = await self.blackboard.get_task(command.task_id)
        if task is None:
            return []

        binding = await self.blackboard.get_binding(task.task_id)
        execution_session = None
        if binding is not None and binding.execution_session_id is not None:
            execution_session = await self.blackboard.get_session(binding.execution_session_id)
        run = await self._select_command_run(execution_session)

        if command.command_type in {TaskCommandType.PAUSE_TASK, TaskCommandType.PREEMPT_TASK}:
            task.status = TaskStatus.PAUSED
            await self._pause_live_run(run)
            if run is not None:
                run.status = RunStatus.PAUSED
                await self.blackboard.put_run(run)
            if binding is not None:
                await self.blackboard.put_binding(
                    binding.model_copy(
                        update={
                            "claimed_by": None,
                            "claim_expires_at": None,
                            "binding_status": BindingStatus.PAUSED,
                        }
                    )
                )
            await self.blackboard.put_summary(
                TaskSummary(
                    task_id=task.task_id,
                    operational_summary=f"Paused: {task.title}",
                    conversational_summary=f"I paused {task.title}.",
                    latest_user_visible_status="paused",
                    needs_user_input=False,
                )
            )
        elif command.command_type == TaskCommandType.CANCEL_TASK:
            task.status = TaskStatus.CANCELLED
            await self._cancel_live_run(run)
            if run is not None:
                run.status = RunStatus.CANCELLED
                await self.blackboard.put_run(run)
            if execution_session is not None and execution_session.active_run_id == (
                run.run_id if run is not None else None
            ):
                execution_session.active_run_id = None
                await self.blackboard.put_session(execution_session)
            if binding is not None:
                await self.blackboard.put_binding(
                    binding.model_copy(
                        update={
                            "claimed_by": None,
                            "claim_expires_at": None,
                            "binding_status": BindingStatus.RELEASED,
                        }
                    )
                )
            await self.blackboard.put_summary(
                TaskSummary(
                    task_id=task.task_id,
                    operational_summary=f"Cancelled: {task.title}",
                    conversational_summary=f"I won't continue with {task.title}.",
                    latest_user_visible_status="cancelled",
                    needs_user_input=False,
                )
            )
            await self._suppress_pending_notifications(task.task_id)
        elif command.command_type in {TaskCommandType.RESUME_TASK, TaskCommandType.RETRY_TASK}:
            task.status = TaskStatus.QUEUED
            if execution_session is not None and run is not None and execution_session.active_run_id == run.run_id:
                execution_session.active_run_id = None
                await self.blackboard.put_session(execution_session)
            if binding is not None:
                await self.blackboard.put_binding(
                    binding.model_copy(
                        update={
                            "claimed_by": None,
                            "claim_expires_at": None,
                            "binding_status": BindingStatus.RELEASED,
                        }
                    )
                )
            await self.blackboard.put_summary(
                TaskSummary(
                    task_id=task.task_id,
                    operational_summary=f"Queued: {task.title}",
                    conversational_summary=f"I queued {task.title} again.",
                    latest_user_visible_status="queued",
                    needs_user_input=False,
                )
            )

        await self.blackboard.put_task(task)
        return [task.task_id]

    async def _select_command_run(
        self,
        execution_session: ExecutionSession | None,
    ) -> ExecutionRun | None:
        if execution_session is None:
            return None
        candidate_run_ids = []
        if execution_session.active_run_id:
            candidate_run_ids.append(execution_session.active_run_id)
        if execution_session.latest_run_id and execution_session.latest_run_id not in candidate_run_ids:
            candidate_run_ids.append(execution_session.latest_run_id)
        for run_id in candidate_run_ids:
            run = await self.blackboard.get_run(run_id)
            if run is not None and run.status in {
                RunStatus.CREATED,
                RunStatus.ASSIGNED,
                RunStatus.RUNNING,
                RunStatus.BLOCKED,
                RunStatus.PAUSED,
            }:
                return run
        return None

    async def _cancel_live_run(self, run) -> None:
        if run is None:
            return
        try:
            executor = self.registry.get(run.executor_type)
        except UnknownExecutorError:
            return
        if not executor.get_capabilities().supports_cancel:
            return
        try:
            await executor.cancel_run(run.run_id)
        except Exception:
            return

    async def _pause_live_run(self, run) -> None:
        if run is None:
            return
        try:
            executor = self.registry.get(run.executor_type)
        except UnknownExecutorError:
            return
        if not executor.get_capabilities().supports_pause:
            return
        try:
            await executor.pause_run(run.run_id)
        except Exception:
            return

    async def _suppress_pending_notifications(self, task_id: str) -> None:
        candidates = await self.blackboard.list_notification_candidates()
        for candidate in candidates:
            if (
                candidate.task_id == task_id
                and candidate.delivery_status == NotificationDeliveryStatus.PENDING
            ):
                await self.blackboard.put_notification_candidate(
                    candidate.model_copy(
                        update={"delivery_status": NotificationDeliveryStatus.SUPPRESSED}
                    )
                )

    async def _run_execution_loop(self) -> None:
        with bind_diagnostic_context(conversation_id=self.session_id):
            while await self._has_runnable_tasks():
                await self.execution_brain.tick()

    async def _has_runnable_tasks(self) -> bool:
        tasks = await self.blackboard.list_tasks()
        return any(task.status in {TaskStatus.CREATED, TaskStatus.QUEUED} for task in tasks)

    def _ensure_communication_pump(self) -> None:
        if self._communication_task is not None and not self._communication_task.done():
            return
        self._communication_task = asyncio.create_task(self._communication_loop())

    def _ensure_snapshot_pump(self) -> None:
        if self._snapshot_task is not None and not self._snapshot_task.done():
            return
        self._blackboard_queue = self.blackboard.subscribe()
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())

    def _ensure_notification_pump(self) -> None:
        if self._notification_task is not None and not self._notification_task.done():
            return
        self._notification_blackboard_queue = self.blackboard.subscribe()
        self._notification_task = asyncio.create_task(self._notification_loop())

    def _ensure_diagnostic_pump(self) -> None:
        if self._diagnostic_task is not None and not self._diagnostic_task.done():
            return
        self._diagnostic_blackboard_queue = self.blackboard.subscribe()
        self._diagnostic_task = asyncio.create_task(self._diagnostic_loop())

    def _wake_notification_pump(self) -> None:
        self._ensure_notification_pump()
        self._notification_wakeup.set()

    async def _communication_loop(self) -> None:
        try:
            while True:
                request = await self._message_queue.get()
                try:
                    await self._handle_message_request(request)
                finally:
                    self._message_queue.task_done()
        except asyncio.CancelledError:
            raise
        finally:
            if asyncio.current_task() is self._communication_task:
                self._communication_task = None

    async def _handle_message_request(self, request: PendingMessageRequest) -> None:
        self._active_assistant_turns += 1
        self._wake_notification_pump()
        try:
            with bind_diagnostic_context(
                conversation_id=self.session_id,
                request_id=request.request_id,
            ):
                try:
                    await self._broadcast_event(
                        AssistantResponseStartedStreamEvent(
                            sequence=self._next_event_sequence(),
                            request_id=request.request_id,
                        )
                    )
                    if self.subscribers:
                        result = await self.communication_brain.generate_reply(
                            self.session_id,
                            request.user_text,
                            on_text_delta=lambda delta: self._broadcast_event(
                                AssistantResponseDeltaStreamEvent(
                                    sequence=self._next_event_sequence(),
                                    request_id=request.request_id,
                                    delta=delta,
                                )
                            ),
                            on_trace=lambda trace: self._record_llm_trace(
                                replace(trace, request_id=request.request_id)
                            ),
                            on_tool_call=lambda record: self._record_tool_call(
                                record.with_request_id(request.request_id)
                            ),
                        )
                    else:
                        result = await self.communication_brain.generate_reply(
                            self.session_id,
                            request.user_text,
                            on_trace=self._record_llm_trace,
                            on_tool_call=self._record_tool_call,
                        )
                except Exception as exc:
                    self.observability.communication.reply_failed(
                        conversation_id=self.session_id,
                        request_id=request.request_id,
                        reason_code=COMMUNICATION_MODEL_FAILURE,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                    assistant_entry = self.history.append_assistant(
                        self.session_id,
                        FALLBACK_ASSISTANT_ERROR_MESSAGE,
                    )
                    result = CommunicationTurnResult(
                        message_id=assistant_entry.message_id,
                        reply_text=FALLBACK_ASSISTANT_ERROR_MESSAGE,
                        conversational_act="model_reply",
                    )
                    await self._broadcast_event(
                        ConversationAppendedStreamEvent(
                            sequence=self._next_event_sequence(),
                            message_id=assistant_entry.message_id,
                            role="assistant",
                            text=FALLBACK_ASSISTANT_ERROR_MESSAGE,
                            source="system_fallback",
                        )
                    )
                    await self._broadcast_event(
                        AssistantResponseFailedStreamEvent(
                            sequence=self._next_event_sequence(),
                            request_id=request.request_id,
                            message=FALLBACK_ASSISTANT_ERROR_MESSAGE,
                        )
                    )
                else:
                    await self._broadcast_event(
                        AssistantResponseCompletedStreamEvent(
                            sequence=self._next_event_sequence(),
                            request_id=request.request_id,
                            message_id=result.message_id,
                            reply_text=result.reply_text,
                            conversational_act=result.conversational_act,
                            affected_task_ids=result.affected_task_ids,
                        )
                    )
                await self.publish_snapshot()
                self.schedule_execution()
                if not request.completion.done():
                    request.completion.set_result(result)
        finally:
            self._active_assistant_turns = max(0, self._active_assistant_turns - 1)
            self._wake_notification_pump()

    async def _snapshot_loop(self) -> None:
        queue = self._blackboard_queue
        if queue is None:
            return
        try:
            while True:
                await queue.get()
                while True:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                await self.publish_snapshot()
        except asyncio.CancelledError:
            raise
        finally:
            self.blackboard.unsubscribe(queue)
            if self._blackboard_queue is queue:
                self._blackboard_queue = None
            if asyncio.current_task() is self._snapshot_task:
                self._snapshot_task = None

    async def _notification_loop(self) -> None:
        queue = self._notification_blackboard_queue
        if queue is None:
            return
        try:
            while True:
                with bind_diagnostic_context(conversation_id=self.session_id):
                    result = await self.notification_manager.process_pending(
                        assistant_busy=self._active_assistant_turns > 0,
                        has_pending_user_messages=not self._message_queue.empty(),
                    )
                queue_task = asyncio.create_task(queue.get())
                wake_task = asyncio.create_task(self._notification_wakeup.wait())
                task_kinds: dict[asyncio.Task, str] = {
                    queue_task: "queue",
                    wake_task: "wake",
                }
                if result.next_due_seconds is not None:
                    timer_task = asyncio.create_task(asyncio.sleep(result.next_due_seconds))
                    task_kinds[timer_task] = "timer"

                done, pending = await asyncio.wait(
                    task_kinds.keys(),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()

                blackboard_events = []
                for task in done:
                    kind = task_kinds[task]
                    if kind == "wake":
                        self._notification_wakeup.clear()
                    elif kind == "queue":
                        blackboard_events.append(task.result())
                while True:
                    try:
                        blackboard_events.append(queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                for event in blackboard_events:
                    with bind_diagnostic_context(conversation_id=self.session_id):
                        await self.notification_manager.handle_blackboard_write(event)
        except asyncio.CancelledError:
            raise
        finally:
            self.blackboard.unsubscribe(queue)
            if self._notification_blackboard_queue is queue:
                self._notification_blackboard_queue = None
            if asyncio.current_task() is self._notification_task:
                self._notification_task = None

    async def _diagnostic_loop(self) -> None:
        queue = self._diagnostic_blackboard_queue
        if queue is None:
            return
        try:
            while True:
                event = await queue.get()
                with bind_diagnostic_context(conversation_id=self.session_id):
                    key = (event.kind.value, event.entity_id)
                    created = key not in self._diagnostic_seen_entities
                    self._diagnostic_seen_entities.add(key)
                    self.observability.blackboard.record_write(
                        event=event,
                        created=created,
                    )
        except asyncio.CancelledError:
            raise
        finally:
            self.blackboard.unsubscribe(queue)
            if self._diagnostic_blackboard_queue is queue:
                self._diagnostic_blackboard_queue = None
            if asyncio.current_task() is self._diagnostic_task:
                self._diagnostic_task = None

    async def _broadcast_event(self, event: SessionStreamEventBase) -> None:
        for queue in list(self.subscribers):
            await queue.put(event)

    async def _record_llm_trace(self, trace: LlmTraceRecord) -> None:
        self.observability.communication.llm_trace(trace)

    async def _record_tool_call(self, record: ToolCallRecord) -> None:
        self.observability.communication.tool_called(
            request_id=record.request_id,
            tool_name=record.tool_name,
            status=record.status,
            args=record.args,
            result_summary=record.result_summary,
            result_preview=record.result_preview,
            affected_task_ids=record.affected_task_ids,
            error_code=record.error.code if record.error is not None else None,
            error_message=record.error.message if record.error is not None else None,
        )

    async def _broadcast_conversation_append(
        self,
        *,
        message_id: str,
        text: str,
        source: str,
    ) -> None:
        await self._broadcast_event(
            ConversationAppendedStreamEvent(
                sequence=self._next_event_sequence(),
                message_id=message_id,
                role="assistant",
                text=text,
                source="notification" if source == "notification" else "system_fallback",
            )
        )

    def _snapshot_event(self, snapshot: SessionSnapshot) -> SnapshotStreamEvent:
        return SnapshotStreamEvent(
            sequence=self._next_event_sequence(),
            snapshot=snapshot,
        )

    def _next_event_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence


def create_session_runtime(
    session_id: str,
    *,
    model: CommunicationModel,
    settings: Settings,
) -> SessionRuntime:
    blackboard = InMemoryBlackboard()
    history = InMemoryConversationHistory()
    registry = ExecutorRegistry()
    observability = build_session_observability(settings)
    registry.register(MockExecutor())
    if settings.acpx_executor_enabled:
        registry.register(
            AcpxExecutor(
                command=settings.acpx_command,
                agent=settings.acpx_agent,
                permission_mode=settings.acpx_permission_mode,
                non_interactive_permissions=settings.acpx_non_interactive_permissions,
                timeout_seconds=settings.acpx_timeout_seconds,
            )
        )
    if settings.codex_executor_enabled:
        registry.register(CodexExecutor(command=settings.codex_command))
    default_executor_type = (
        "acpx"
        if settings.acpx_executor_enabled
        else "codex" if settings.codex_executor_enabled else "mock"
    )
    # Load user-defined personas from ~/.synapse/personas.yaml into the blackboard.
    tool_registry = build_default_tool_registry(
        blackboard,
        executor_types=registry.list_executor_types(),
        default_executor_type=default_executor_type,
    )
    communication_brain = CommunicationBrain(
        blackboard,
        model,
        history=history,
        tool_registry=tool_registry,
        executor_capabilities=registry.list_capabilities(),
        default_executor_type=default_executor_type,
        observability=observability.communication,
    )
    execution_brain = ExecutionBrain(
        blackboard,
        registry,
        worker_id=f"worker-{session_id}",
        default_executor_type=default_executor_type,
        observability=observability.execution,
    )
    notification_manager = NotificationManager(
        blackboard,
        communication_brain,
        conversation_id=session_id,
        observability=observability.notification,
    )
    runtime = SessionRuntime(
        session_id=session_id,
        blackboard=blackboard,
        history=history,
        registry=registry,
        communication_brain=communication_brain,
        execution_brain=execution_brain,
        notification_manager=notification_manager,
        observability=observability,
    )
    control_task_handler = tool_registry.get("control_task").handler
    if hasattr(control_task_handler, "set_apply_callback"):
        control_task_handler.set_apply_callback(runtime.apply_command)
    communication_brain.set_trace_callback(runtime._record_llm_trace)
    notification_manager.set_conversation_event_callback(runtime._broadcast_conversation_append)
    runtime.start_notification_processing()
    runtime._ensure_diagnostic_pump()
    # Load personas from persistent config into the blackboard.
    for persona in load_personas_from_file():
        blackboard._personas[persona.persona_id] = persona
    return runtime
