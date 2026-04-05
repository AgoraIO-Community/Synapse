from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import uuid4

from synopse.blackboard import InMemoryBlackboard
from synopse.communication import CommunicationBrain, InMemoryConversationHistory
from synopse.communication.model import CommunicationModel
from synopse.communication.tools import build_default_tool_registry
from synopse.communication.resolver import TaskResolver
from synopse.execution import ExecutionBrain
from synopse.executor_adapters.mock import MockExecutor
from synopse.executor_core import ExecutorRegistry
from synopse.protocol import TaskCommand, TaskCommandType, TaskStatus

from .models import ConversationHistoryEntryModel, SessionSnapshot


@dataclass(slots=True)
class SessionRuntime:
    session_id: str
    blackboard: InMemoryBlackboard
    history: InMemoryConversationHistory
    registry: ExecutorRegistry
    communication_brain: CommunicationBrain
    execution_brain: ExecutionBrain
    subscribers: list[asyncio.Queue[SessionSnapshot]] = field(default_factory=list)

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

    def subscribe(self) -> asyncio.Queue[SessionSnapshot]:
        queue: asyncio.Queue[SessionSnapshot] = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[SessionSnapshot]) -> None:
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    async def publish_snapshot(self) -> SessionSnapshot:
        snapshot = await self.snapshot()
        for queue in list(self.subscribers):
            await queue.put(snapshot)
        return snapshot

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
        return await self.execution_brain.tick()


def create_session_runtime(
    session_id: str,
    *,
    model: CommunicationModel,
) -> SessionRuntime:
    blackboard = InMemoryBlackboard()
    history = InMemoryConversationHistory()
    registry = ExecutorRegistry()
    registry.register(MockExecutor())
    communication_brain = CommunicationBrain(
        blackboard,
        model,
        history=history,
        tool_registry=build_default_tool_registry(
            blackboard,
            executor_types=registry.list_executor_types(),
        ),
    )
    execution_brain = ExecutionBrain(blackboard, registry, worker_id=f"worker-{session_id}")
    return SessionRuntime(
        session_id=session_id,
        blackboard=blackboard,
        history=history,
        registry=registry,
        communication_brain=communication_brain,
        execution_brain=execution_brain,
    )
