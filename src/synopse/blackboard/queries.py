from __future__ import annotations

from synopse.protocol import Task, TaskCommand, TaskMutation, TaskStatus

from .interfaces import BlackboardStore


class BlackboardQueryService:
    def __init__(self, store: BlackboardStore) -> None:
        self._store = store

    async def list_tasks_by_status(self, *statuses: TaskStatus) -> list[Task]:
        tasks = await self._store.list_tasks()
        if not statuses:
            return tasks
        wanted = set(statuses)
        return [task for task in tasks if task.status in wanted]

    async def list_runnable_tasks(self) -> list[Task]:
        return await self.list_tasks_by_status(TaskStatus.CREATED, TaskStatus.QUEUED)

    async def list_active_tasks(self) -> list[Task]:
        return await self.list_tasks_by_status(TaskStatus.RUNNING, TaskStatus.WAITING_USER_INPUT)

    async def get_latest_mutation(self, task_id: str) -> TaskMutation | None:
        mutations = await self._store.list_mutations(task_id)
        return mutations[-1] if mutations else None

    async def get_latest_command(self, task_id: str) -> TaskCommand | None:
        commands = await self._store.list_commands(task_id)
        return commands[-1] if commands else None
