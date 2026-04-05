from __future__ import annotations

from dataclasses import dataclass

from synopse.blackboard import BlackboardQueryService, BlackboardStore
from synopse.protocol import Task, TaskSummary

from .history import ConversationEntry, InMemoryConversationHistory


@dataclass(slots=True)
class CommunicationContext:
    conversation_id: str
    recent_history: list[ConversationEntry]
    tasks: list[Task]
    summaries: dict[str, TaskSummary | None]
    available_tools: list[str]


class CommunicationContextBuilder:
    def __init__(
        self,
        store: BlackboardStore,
        history: InMemoryConversationHistory,
    ) -> None:
        self._store = store
        self._history = history
        self._queries = BlackboardQueryService(store)

    async def build(
        self,
        conversation_id: str,
        *,
        available_tools: list[str],
        history_limit: int = 10,
    ) -> CommunicationContext:
        tasks = await self._store.list_tasks()
        summaries = {
            task.task_id: await self._store.get_summary(task.task_id)
            for task in tasks
        }
        return CommunicationContext(
            conversation_id=conversation_id,
            recent_history=self._history.get_recent(conversation_id, limit=history_limit),
            tasks=tasks,
            summaries=summaries,
            available_tools=available_tools,
        )
