from __future__ import annotations

from synopse.protocol import Task


class TaskResolver:
    def resolve(
        self,
        tasks: list[Task],
        *,
        task_id: str | None = None,
        reference: str | None = None,
    ) -> Task | None:
        if task_id:
            for task in tasks:
                if task.task_id == task_id:
                    return task
        if reference:
            needle = reference.lower()
            for task in reversed(tasks):
                if needle in task.title.lower() or needle in task.goal.lower():
                    return task
        return tasks[-1] if tasks else None
