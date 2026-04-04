from __future__ import annotations

from runtime.protocols.tasks import Task, TaskReference, TaskReferenceRelation, TaskReferenceType, TaskStatus
from runtime.shared_blackboard.models import SessionState


ACTIVE_STATUSES = {
    TaskStatus.QUEUED,
    TaskStatus.RUNNING,
    TaskStatus.BLOCKED,
    TaskStatus.PAUSED,
}


def resolve_task_reference(session: SessionState, reference: TaskReference | None) -> Task | None:
    tasks = list(session.task_registry.values())
    if not tasks or reference is None:
        return None

    if reference.reference_type == TaskReferenceType.TASK_ID and reference.value:
        return session.task_registry.get(reference.value)

    if reference.reference_type == TaskReferenceType.LATEST_ACTIVE:
        active = [task for task in tasks if task.status in ACTIVE_STATUSES]
        active.sort(key=lambda item: item.updated_at, reverse=True)
        return active[0] if active else None

    if reference.reference_type == TaskReferenceType.LATEST_CREATED:
        tasks.sort(key=lambda item: item.created_at, reverse=True)
        return tasks[0] if tasks else None

    if reference.reference_type == TaskReferenceType.BY_GOAL_MATCH and reference.value:
        needle = reference.value.lower()
        for task in sorted(tasks, key=lambda item: item.updated_at, reverse=True):
            if needle in task.goal.lower() or needle in task.title.lower():
                return task

    if reference.reference_type == TaskReferenceType.BY_RELATION:
        current = resolve_task_reference(
            session,
            TaskReference(reference_type=TaskReferenceType.LATEST_ACTIVE),
        )
        if current is None:
            return None
        if reference.relation == TaskReferenceRelation.CURRENT:
            return current
        if reference.relation == TaskReferenceRelation.PARENT and current.parent_task_id:
            return session.task_registry.get(current.parent_task_id)
        if reference.relation == TaskReferenceRelation.CHILD:
            for task in tasks:
                if task.parent_task_id == current.task_id:
                    return task
        if reference.relation == TaskReferenceRelation.SIBLING and current.parent_task_id:
            for task in tasks:
                if (
                    task.task_id != current.task_id
                    and task.parent_task_id == current.parent_task_id
                ):
                    return task

    return None
