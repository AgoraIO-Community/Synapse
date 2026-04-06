from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from synopse.blackboard import InMemoryBlackboard
from synopse.communication import CommunicationBrain, InMemoryConversationHistory
from synopse.communication.model import CommunicationModel
from synopse.communication.tools import build_default_tool_registry
from synopse.communication.types import CommunicationTurnResult
from synopse.execution import ExecutionBrain
from synopse.executor_adapters.codex import CodexExecutor
from synopse.executor_adapters.mock import MockExecutor
from synopse.executor_core import ExecutorRegistry
from synopse.protocol import TaskCommand, TaskCommandType, TaskStatus

from .config import Settings
from .models import (
    ActionAcceptedStreamEvent,
    ActionRejectedStreamEvent,
    AssistantResponseCompletedStreamEvent,
    AssistantResponseDeltaStreamEvent,
    AssistantResponseFailedStreamEvent,
    AssistantResponseStartedStreamEvent,
    ConversationHistoryEntryModel,
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
    subscribers: list[asyncio.Queue[SessionStreamEventBase]] = field(default_factory=list)
    _message_queue: asyncio.Queue[PendingMessageRequest] = field(default_factory=asyncio.Queue)
    _execution_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _communication_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _snapshot_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _blackboard_queue: asyncio.Queue | None = field(default=None, init=False, repr=False)
    _next_sequence: int = field(default=1, init=False, repr=False)

    async def snapshot(self) -> SessionSnapshot:
        tasks = await self.blackboard.list_tasks()
        mutations = await self.blackboard.list_all_mutations()
        commands = await self.blackboard.list_all_commands()
        sessions = await self.blackboard.list_sessions()
        runs = await self.blackboard.list_runs()
        bindings = await self.blackboard.list_bindings()
        summaries = [
            summary
            for summary in [await self.blackboard.get_summary(task.task_id) for task in tasks]
            if summary is not None
        ]
        recent_writes = await self.blackboard.list_recent_writes()
        history = [
            ConversationHistoryEntryModel(
                role=entry.role,
                text=entry.text,
                message_id=entry.message_id,
            )
            for entry in self.history.get_recent(self.session_id, limit=50)
        ]
        return SessionSnapshot(
            session_id=self.session_id,
            tasks=tasks,
            mutations=mutations,
            commands=commands,
            execution_sessions=sessions,
            execution_runs=runs,
            bindings=bindings,
            summaries=summaries,
            recent_blackboard_writes=recent_writes,
            conversation_history=history,
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
        if start_processing:
            self._ensure_communication_pump()
        return user_entry.message_id, completion

    def start_message_processing(self) -> None:
        self._ensure_communication_pump()

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
        if self._execution_task is not None and not self._execution_task.done():
            return
        self._execution_task = asyncio.create_task(self._run_execution_loop())

    async def apply_command(self, command: TaskCommand) -> list[str]:
        await self.blackboard.append_command(command)
        task = await self.blackboard.get_task(command.task_id)
        if task is None:
            return []

        if command.command_type in {TaskCommandType.PAUSE_TASK, TaskCommandType.PREEMPT_TASK}:
            task.status = TaskStatus.PAUSED
        elif command.command_type == TaskCommandType.CANCEL_TASK:
            task.status = TaskStatus.CANCELLED
        elif command.command_type in {TaskCommandType.RESUME_TASK, TaskCommandType.RETRY_TASK}:
            task.status = TaskStatus.QUEUED

        await self.blackboard.put_task(task)
        return [task.task_id]

    async def _run_execution_loop(self) -> None:
        try:
            while await self._has_runnable_tasks():
                await self.execution_brain.tick()
        finally:
            self._execution_task = None

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
        await self._broadcast_event(
            AssistantResponseStartedStreamEvent(
                sequence=self._next_event_sequence(),
                request_id=request.request_id,
            )
        )
        try:
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
                )
            else:
                result = await self.communication_brain.generate_reply(
                    self.session_id,
                    request.user_text,
                )
        except Exception:
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

    async def _broadcast_event(self, event: SessionStreamEventBase) -> None:
        for queue in list(self.subscribers):
            await queue.put(event)

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
    registry.register(MockExecutor())
    if settings.codex_executor_enabled:
        registry.register(CodexExecutor(command=settings.codex_command))
    default_executor_type = "codex" if settings.codex_executor_enabled else "mock"
    communication_brain = CommunicationBrain(
        blackboard,
        model,
        history=history,
        tool_registry=build_default_tool_registry(
            blackboard,
            executor_types=registry.list_executor_types(),
            default_executor_type=default_executor_type,
        ),
        executor_capabilities=registry.list_capabilities(),
        default_executor_type=default_executor_type,
    )
    execution_brain = ExecutionBrain(
        blackboard,
        registry,
        worker_id=f"worker-{session_id}",
        default_executor_type=default_executor_type,
    )
    return SessionRuntime(
        session_id=session_id,
        blackboard=blackboard,
        history=history,
        registry=registry,
        communication_brain=communication_brain,
        execution_brain=execution_brain,
    )
