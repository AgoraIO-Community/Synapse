from __future__ import annotations

from runtime.infrastructure.ids import new_id
from runtime.protocols.runtime import RuntimeAction
from runtime.protocols.tasks import Task


def build_task(action: RuntimeAction, *, message_id: str, executor_id: str) -> Task:
    task_id = new_id("task")
    goal = action.payload["goal"]
    input_context = dict(action.payload.get("input_context", {}))
    input_context["requires_executor_capability"] = True
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
        input_context=input_context,
    )
