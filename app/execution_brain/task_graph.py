from __future__ import annotations

from app.infrastructure.ids import new_id
from app.protocols.runtime import RuntimeAction
from app.protocols.tasks import Task


def build_task(action: RuntimeAction, *, message_id: str, executor_id: str) -> Task:
    task_id = new_id("task")
    goal = action.payload["goal"]
    return Task(
        task_id=task_id,
        root_task_id=task_id,
        parent_task_id=None,
        title=action.payload.get("title", goal[:80]),
        goal=goal,
        assigned_executor=executor_id,
        candidate_executors=[executor_id],
        created_from_message_id=message_id,
        latest_instruction=goal,
        input_context=action.payload.get("input_context", {}),
    )
