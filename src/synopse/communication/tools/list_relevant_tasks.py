from __future__ import annotations

from synopse.blackboard import BlackboardStore
from synopse.communication.resolver import TaskResolver


class ListRelevantTasksTool:
    name = "list_relevant_tasks"

    def __init__(self, store: BlackboardStore) -> None:
        self._store = store
        self._resolver = TaskResolver()

    async def __call__(
        self,
        *,
        reference: str,
        limit: int = 5,
    ) -> dict[str, object]:
        tasks = await self._store.list_tasks()
        candidates = self._resolver.list_relevant(tasks, reference=reference, limit=max(1, min(limit, 5)))
        summaries = {
            task.task_id: await self._store.get_summary(task.task_id)
            for task in [candidate.task for candidate in candidates]
        }
        return {
            "reference": reference,
            "matches": [
                {
                    "task_id": candidate.task.task_id,
                    "title": candidate.task.title,
                    "goal": candidate.task.goal,
                    "status": candidate.task.status.value,
                    "latest_instruction": candidate.task.latest_instruction,
                    "latest_user_visible_status": (
                        summaries[candidate.task.task_id].latest_user_visible_status
                        if summaries[candidate.task.task_id] is not None
                        else None
                    ),
                    "conversational_summary": (
                        summaries[candidate.task.task_id].conversational_summary
                        if summaries[candidate.task.task_id] is not None
                        else None
                    ),
                    "match_reasons": candidate.reasons,
                }
                for candidate in candidates
            ],
        }
