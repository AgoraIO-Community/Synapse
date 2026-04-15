from synapse.execution import SummaryManager
from synapse.protocol import ExecutionRun, RunStatus, Task


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
