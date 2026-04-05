from synopse.communication.resolver import TaskResolver
from synopse.protocol import Task


def test_task_resolver_prefers_explicit_reference_then_latest():
    resolver = TaskResolver()
    tasks = [
        Task(task_id="task_1", root_task_id="task_1", title="Draft email", goal="Draft email"),
        Task(task_id="task_2", root_task_id="task_2", title="Book flight", goal="Book flight"),
    ]

    assert resolver.resolve(tasks, reference="email").task_id == "task_1"
    assert resolver.resolve(tasks).task_id == "task_2"
