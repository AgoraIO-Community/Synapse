from __future__ import annotations

from uuid import uuid4

from synopse.blackboard import BlackboardStore
from synopse.protocol import MutationType, Task, TaskMutation


class CreateTaskTool:
    name = "create_task"

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store

    async def __call__(
        self,
        *,
        title: str,
        goal: str,
        preferred_executor: str | None = None,
        requires_confirmation: bool = False,
    ) -> Task:
        task_id = f"task-{uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            root_task_id=task_id,
            title=title,
            goal=goal,
            preferred_executor=preferred_executor,
            requires_confirmation=requires_confirmation,
        )
        await self._store.put_task(task)
        await self._store.append_mutation(
            TaskMutation(
                mutation_id=f"mut-{uuid4().hex[:8]}",
                task_id=task_id,
                mutation_type=MutationType.CREATE,
                patch={"title": title, "goal": goal},
                created_by="communication_brain",
            )
        )
        saved = await self._store.get_task(task_id)
        return saved or task
