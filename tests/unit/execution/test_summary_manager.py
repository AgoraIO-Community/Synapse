from newbro.execution import SummaryManager
from newbro.protocol import ExecutionRun, RunStatus, Task, TaskStatus


def test_summary_manager_builds_blocked_summary():
    manager = SummaryManager()
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Blocked task",
        goal="Blocked task",
    )
    run = ExecutionRun(
        run_id="run_1",
        task_id="task_1",
        execution_session_id="sess_1",
        executor_type="mock",
        status=RunStatus.BLOCKED,
        block_reason="Need confirmation.",
    )

    summary = manager.build_summary(task, run)
    assert summary.needs_user_input is True
    assert summary.latest_user_visible_status == "waiting_user_input"


def test_summary_manager_prefers_task_queued_status_for_follow_up_resume():
    manager = SummaryManager()
    task = Task(
        task_id="task_2",
        root_task_id="task_2",
        title="Queued task",
        goal="Queued task",
        status=TaskStatus.QUEUED,
    )
    run = ExecutionRun(
        run_id="run_2",
        task_id="task_2",
        execution_session_id="sess_2",
        executor_type="mock",
        status=RunStatus.BLOCKED,
        block_reason="Need confirmation.",
    )

    summary = manager.build_summary(task, run)

    assert summary.needs_user_input is False
    assert summary.latest_user_visible_status == "queued"
