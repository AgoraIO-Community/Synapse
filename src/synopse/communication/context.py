from __future__ import annotations

from dataclasses import dataclass

from synopse.blackboard import BlackboardQueryService, BlackboardStore
from synopse.executor_core import ExecutorCapabilities
from synopse.protocol import Task, TaskStatus, TaskSummary

from .history import ConversationEntry, InMemoryConversationHistory

DEFAULT_HISTORY_LIMIT = 30
ACTIVE_CONTEXT_TASK_LIMIT = 5
RECENT_CONTEXT_TASK_LIMIT = 5


@dataclass(slots=True)
class CommunicationTaskBrief:
    task_id: str
    title: str
    goal: str
    status: str
    priority: int
    latest_instruction: str | None
    conversational_summary: str | None
    latest_user_visible_status: str | None
    note_count: int
    constraint_count: int


@dataclass(slots=True)
class ExecutorRuntimeSummary:
    has_real_executor: bool
    available_executor_types: list[str]
    default_executor_type: str | None
    executors: list[dict[str, object]]


@dataclass(slots=True)
class CommunicationContext:
    conversation_id: str
    recent_history: list[ConversationEntry]
    tasks: list[Task]
    summaries: dict[str, TaskSummary | None]
    active_tasks: list[CommunicationTaskBrief]
    recent_tasks: list[CommunicationTaskBrief]
    executor_runtime: ExecutorRuntimeSummary
    available_tools: list[str]


class CommunicationContextBuilder:
    def __init__(
        self,
        store: BlackboardStore,
        history: InMemoryConversationHistory,
        *,
        executor_capabilities: list[ExecutorCapabilities] | None = None,
        default_executor_type: str | None = None,
    ) -> None:
        self._store = store
        self._history = history
        self._queries = BlackboardQueryService(store)
        self._executor_capabilities = list(executor_capabilities or [])
        self._default_executor_type = default_executor_type

    async def build(
        self,
        conversation_id: str,
        *,
        available_tools: list[str],
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> CommunicationContext:
        tasks = await self._store.list_tasks()
        summaries = {
            task.task_id: await self._store.get_summary(task.task_id)
            for task in tasks
        }
        active_tasks = [
            self._build_task_brief(task, summaries.get(task.task_id))
            for task in tasks
            if task.status
            in {
                TaskStatus.CREATED,
                TaskStatus.QUEUED,
                TaskStatus.RUNNING,
                TaskStatus.WAITING_USER_INPUT,
                TaskStatus.PAUSED,
            }
        ][:ACTIVE_CONTEXT_TASK_LIMIT]
        recent_tasks = [
            self._build_task_brief(task, summaries.get(task.task_id))
            for task in reversed(tasks[-RECENT_CONTEXT_TASK_LIMIT:])
        ]
        return CommunicationContext(
            conversation_id=conversation_id,
            recent_history=self._history.get_recent(conversation_id, limit=history_limit),
            tasks=tasks,
            summaries=summaries,
            active_tasks=active_tasks,
            recent_tasks=recent_tasks,
            executor_runtime=self._build_executor_runtime_summary(),
            available_tools=available_tools,
        )

    def _build_task_brief(
        self,
        task: Task,
        summary: TaskSummary | None,
    ) -> CommunicationTaskBrief:
        notes = task.metadata.get("notes", [])
        constraints = task.metadata.get("constraints", [])
        return CommunicationTaskBrief(
            task_id=task.task_id,
            title=task.title,
            goal=task.goal,
            status=task.status.value,
            priority=task.priority,
            latest_instruction=task.latest_instruction,
            conversational_summary=summary.conversational_summary if summary is not None else None,
            latest_user_visible_status=(
                summary.latest_user_visible_status if summary is not None else None
            ),
            note_count=len(notes) if isinstance(notes, list) else 0,
            constraint_count=len(constraints) if isinstance(constraints, list) else 0,
        )

    def _build_executor_runtime_summary(self) -> ExecutorRuntimeSummary:
        available_executor_types = [
            capability.executor_type for capability in self._executor_capabilities
        ]
        return ExecutorRuntimeSummary(
            has_real_executor=any(
                capability.executor_type != "mock"
                for capability in self._executor_capabilities
            ),
            available_executor_types=available_executor_types,
            default_executor_type=self._default_executor_type,
            executors=[
                {
                    "executor_type": capability.executor_type,
                    "is_mock": capability.executor_type == "mock",
                    "supports_follow_up": capability.supports_follow_up,
                    "supports_resume": capability.supports_resume,
                    "supports_pause": capability.supports_pause,
                    "supports_cancel": capability.supports_cancel,
                    "supports_setup": capability.supports_setup,
                }
                for capability in self._executor_capabilities
            ],
        )
