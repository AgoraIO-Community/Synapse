from __future__ import annotations

from synopse.blackboard import BlackboardStore
from synopse.protocol import Task


class ListTasksTool:
    name = "list_tasks"

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store

    async def __call__(self, *, query: str | None = None) -> list[Task]:
        tasks = await self._store.list_tasks()
        if not query:
            return tasks
        needle = query.lower()
        return [
            task
            for task in tasks
            if needle in task.title.lower() or needle in task.goal.lower()
        ]
