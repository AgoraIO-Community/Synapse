from __future__ import annotations

import asyncio
from collections import defaultdict

from synapse.observability.context import get_diagnostic_context
from synapse.protocol import (
    ExecutionRun,
    ExecutionSession,
    NotificationCandidate,
    SessionBinding,
    Task,
    TaskCommand,
    TaskExecutionMode,
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
        self._mutations: list[TaskMutation] = []
        self._commands: list[TaskCommand] = []
        self._sessions: dict[str, ExecutionSession] = {}
        self._runs: dict[str, ExecutionRun] = {}
        self._bindings_by_task: dict[str, SessionBinding] = {}
        self._summaries_by_task: dict[str, TaskSummary] = {}
        self._execution_modes_by_task: dict[str, TaskExecutionMode] = {}
        self._notification_candidates: dict[str, NotificationCandidate] = {}
        self._notification_candidate_order: list[str] = []
        self._recent_writes: list[BlackboardWriteEvent] = []
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
            self._mutations.append(mutation)
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.MUTATION,
                entity_id=mutation.mutation_id,
                task_id=mutation.task_id,
                payload={
                    "mutation_id": mutation.mutation_id,
                    "mutation_type": mutation.mutation_type.value,
                    "created_by": mutation.created_by,
                    "urgency": mutation.urgency,
                    "effective_scope": mutation.effective_scope,
                    "requires_replan": mutation.requires_replan,
                    "patch": mutation.patch,
                },
            )
        )

    async def list_mutations(self, task_id: str) -> list[TaskMutation]:
        return list(self._mutations_by_task.get(task_id, []))

    async def list_all_mutations(self) -> list[TaskMutation]:
        return list(self._mutations)

    async def append_command(self, command: TaskCommand) -> None:
        async with self._lock:
            self._commands_by_task[command.task_id].append(command)
            self._commands.append(command)
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.COMMAND,
                entity_id=command.command_id,
                task_id=command.task_id,
                payload={
                    "command_id": command.command_id,
                    "command_type": command.command_type.value,
                    "created_by": command.created_by,
                    "reason": command.reason,
                    "payload": command.payload,
                },
            )
        )

    async def list_commands(self, task_id: str) -> list[TaskCommand]:
        return list(self._commands_by_task.get(task_id, []))

    async def list_all_commands(self) -> list[TaskCommand]:
        return list(self._commands)

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

    async def put_execution_mode(self, execution_mode: TaskExecutionMode) -> None:
        async with self._lock:
            self._execution_modes_by_task[execution_mode.task_id] = execution_mode
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.EXECUTION_MODE,
                entity_id=execution_mode.task_id,
                task_id=execution_mode.task_id,
                payload={"mode": execution_mode.mode.value},
            )
        )

    async def get_execution_mode(self, task_id: str) -> TaskExecutionMode | None:
        return self._execution_modes_by_task.get(task_id)

    async def list_execution_modes(self) -> list[TaskExecutionMode]:
        return list(self._execution_modes_by_task.values())

    async def put_notification_candidate(self, candidate: NotificationCandidate) -> None:
        async with self._lock:
            if candidate.candidate_id not in self._notification_candidates:
                self._notification_candidate_order.append(candidate.candidate_id)
            self._notification_candidates[candidate.candidate_id] = candidate
        await self._publish(
            BlackboardWriteEvent(
                kind=BlackboardWriteKind.NOTIFICATION,
                entity_id=candidate.candidate_id,
                task_id=candidate.task_id,
                payload={
                    "candidate_type": candidate.candidate_type.value,
                    "delivery_status": candidate.delivery_status.value,
                },
            )
        )

    async def get_notification_candidate(self, candidate_id: str) -> NotificationCandidate | None:
        return self._notification_candidates.get(candidate_id)

    async def list_notification_candidates(self) -> list[NotificationCandidate]:
        return [
            self._notification_candidates[candidate_id]
            for candidate_id in self._notification_candidate_order
            if candidate_id in self._notification_candidates
        ]

    async def list_recent_writes(self, limit: int = 50) -> list[BlackboardWriteEvent]:
        return list(self._recent_writes[-limit:])

    def subscribe(self) -> asyncio.Queue[BlackboardWriteEvent]:
        return self._subscriptions.subscribe()

    def unsubscribe(self, queue: asyncio.Queue[BlackboardWriteEvent]) -> None:
        self._subscriptions.unsubscribe(queue)

    async def _publish(self, event: BlackboardWriteEvent) -> None:
        if event.request_id is None:
            event.request_id = get_diagnostic_context().request_id
        self._recent_writes.append(event)
        await self._subscriptions.publish(event)
