from __future__ import annotations

from runtime.infrastructure.ids import new_id
from runtime.protocols.runtime import RuntimeAction
from runtime.protocols.tasks import Task


def build_task(action: RuntimeAction, *, message_id: str, executor_id: str) -> Task:
    task_id = new_id("task")
    goal = action.payload.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("create_task payload requires a non-empty goal.")
    resolved_goal = goal.strip()
    title = action.payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("create_task payload requires a non-empty title.")
    resolved_title = title.strip()
    input_context = dict(action.payload.get("input_context", {}))
    input_context.setdefault("requires_executor_capability", True)
    return Task(
        task_id=task_id,
        root_task_id=task_id,
        parent_task_id=None,
        title=resolved_title,
        goal=resolved_goal,
        assigned_executor=executor_id,
        candidate_executors=[executor_id],
        created_from_message_id=message_id,
        latest_instruction=resolved_goal,
        input_context=input_context,
    )
