from synopse.communication.resolver import TaskResolver
from synopse.protocol import Task, TaskStatus


def test_task_resolver_returns_resolved_match_for_unique_reference():
    resolver = TaskResolver()
    tasks = [
        Task(task_id="task_1", root_task_id="task_1", title="Draft email", goal="Draft email"),
        Task(task_id="task_2", root_task_id="task_2", title="Book flight", goal="Book flight"),
    ]

    resolution = resolver.resolve(tasks, reference="email")

    assert resolution.status == "resolved"
    assert resolution.task is not None
    assert resolution.task.task_id == "task_1"


def test_task_resolver_marks_ambiguous_reference_instead_of_falling_back():
    resolver = TaskResolver()
    tasks = [
        Task(task_id="task_1", root_task_id="task_1", title="Draft email", goal="Reply to Alice"),
        Task(task_id="task_2", root_task_id="task_2", title="Send email", goal="Follow up with Bob"),
    ]

    resolution = resolver.resolve(tasks, reference="email")

    assert resolution.status == "ambiguous"
    assert resolution.task is None
    assert [candidate.task.task_id for candidate in resolution.candidates] == ["task_2", "task_1"]


def test_task_resolver_returns_not_found_when_no_reference_is_provided():
    resolver = TaskResolver()
    tasks = [
        Task(
            task_id="task_1",
            root_task_id="task_1",
            title="Draft email",
            goal="Draft email",
            status=TaskStatus.RUNNING,
        )
    ]

    resolution = resolver.resolve(tasks)

    assert resolution.status == "not_found"
