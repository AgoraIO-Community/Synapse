from __future__ import annotations

import asyncio
from collections import defaultdict

from synopse.protocol import (
    ExecutionRun,
    ExecutionSession,
    SessionBinding,
    Task,
    TaskCommand,
    TaskMutation,
    TaskSummary,
)

from ..interfaces import BlackboardStore
from ..revisions import bump_task_revision
from ..store import BlackboardWriteEvent, BlackboardWriteKind
from ..subscriptions import SubscriptionManager


class InMemoryBlackboard(BlackboardStore):
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._mutations_by_task: dict[str, list[TaskMutation]] = defaultdict(list)
        self._commands_by_task: dict[str, list[TaskCommand]] = defaultdict(list)
        self._sessions: dict[str, ExecutionSession] = {}
        self._runs: dict[str, ExecutionRun] = {}
        self._bindings_by_task: dict[str, SessionBinding] = {}
        self._summaries_by_task: dict[str, TaskSummary] = {}
        self._subscriptions = SubscriptionManager()
        self._lock = asyncio.Lock()

    async def put_task(self, task: Task) -> None:
        async with self._lock:
            self._tasks[task.task_id] = task
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.TASK,
                entity_id=task.task_id,
                task_id=task.task_id,
            )
        )

    async def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    async def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    async def append_mutation(self, mutation: TaskMutation) -> None:
        async with self._lock:
            if mutation.task_id is not None:
                self._mutations_by_task[mutation.task_id].append(mutation)
                task = self._tasks.get(mutation.task_id)
                if task is not None:
                    bump_task_revision(task)
            else:
                self._mutations_by_task[""].append(mutation)
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.MUTATION,
                entity_id=mutation.mutation_id,
                task_id=mutation.task_id,
            )
        )

    async def list_mutations(self, task_id: str) -> list[TaskMutation]:
        return list(self._mutations_by_task.get(task_id, []))

    async def append_command(self, command: TaskCommand) -> None:
        async with self._lock:
            self._commands_by_task[command.task_id].append(command)
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.COMMAND,
                entity_id=command.command_id,
                task_id=command.task_id,
            )
        )

    async def list_commands(self, task_id: str) -> list[TaskCommand]:
        return list(self._commands_by_task.get(task_id, []))

    async def put_run(self, run: ExecutionRun) -> None:
        async with self._lock:
            self._runs[run.run_id] = run
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.RUN,
                entity_id=run.run_id,
                task_id=run.task_id,
            )
        )

    async def get_run(self, run_id: str) -> ExecutionRun | None:
        return self._runs.get(run_id)

    async def list_runs(self) -> list[ExecutionRun]:
        return list(self._runs.values())

    async def put_session(self, session: ExecutionSession) -> None:
        async with self._lock:
            self._sessions[session.execution_session_id] = session
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.SESSION,
                entity_id=session.execution_session_id,
                task_id=session.task_id,
            )
        )

    async def get_session(self, execution_session_id: str) -> ExecutionSession | None:
        return self._sessions.get(execution_session_id)

    async def list_sessions(self) -> list[ExecutionSession]:
        return list(self._sessions.values())

    async def put_binding(self, binding: SessionBinding) -> None:
        async with self._lock:
            self._bindings_by_task[binding.task_id] = binding
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.BINDING,
                entity_id=binding.session_id,
                task_id=binding.task_id,
            )
        )

    async def get_binding(self, task_id: str) -> SessionBinding | None:
        return self._bindings_by_task.get(task_id)

    async def list_bindings(self) -> list[SessionBinding]:
        return list(self._bindings_by_task.values())

    async def put_summary(self, summary: TaskSummary) -> None:
        async with self._lock:
            self._summaries_by_task[summary.task_id] = summary
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.SUMMARY,
                entity_id=summary.task_id,
                task_id=summary.task_id,
            )
        )

    async def get_summary(self, task_id: str) -> TaskSummary | None:
        return self._summaries_by_task.get(task_id)

    def subscribe(self) -> asyncio.Queue[BlackboardWriteEvent]:
        return self._subscriptions.subscribe()

    def unsubscribe(self, queue: asyncio.Queue[BlackboardWriteEvent]) -> None:
        self._subscriptions.unsubscribe(queue)

    async def _publish(self, event: BlackboardWriteEvent) -> None:
        await self._subscriptions.publish(event)
