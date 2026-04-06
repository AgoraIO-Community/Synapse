from synopse.protocol import (
    AssignmentLease,
    ConversationEffect,
    ExecutionMode,
    ExecutionRun,
    ExecutionSession,
    Interruption,
    InterruptionType,
    NotificationCandidate,
    NotificationCandidateType,
    NotificationDeliveryStatus,
    NotificationPriority,
    RunStatus,
    SessionBinding,
    Task,
    TaskCommand,
    TaskCommandType,
    TaskExecutionMode,
    TaskMutation,
    TaskStatus,
    TaskSummary,
)


def test_task_model_defaults():
    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Investigate bug",
        goal="Investigate the reported issue",
    )

    assert task.status == TaskStatus.CREATED
    assert task.priority == 5
    assert task.task_revision == 0


def test_mutation_and_command_models():
    mutation = TaskMutation(
        mutation_id="mut_1",
        task_id="task_1",
        mutation_type="update",
        patch={"tone": "casual"},
        created_by="communication_brain",
    )
    command = TaskCommand(
        command_id="cmd_1",
        task_id="task_1",
        command_type=TaskCommandType.PAUSE_TASK,
        created_by="communication_brain",
    )

    assert mutation.mutation_type.value == "update"
    assert command.command_type.value == "pause_task"


def test_execution_lineage_models():
    session = ExecutionSession(
        execution_session_id="sess_1",
        task_id="task_1",
        base_executor_id="codex",
    )
    run = ExecutionRun(
        run_id="run_1",
        task_id="task_1",
        execution_session_id="sess_1",
        executor_type="codex",
    )
    binding = SessionBinding(
        task_id="task_1",
        execution_session_id="sess_1",
        session_id="agent_sess_1",
    )

    assert session.active_run_id is None
    assert run.status == RunStatus.CREATED
    assert binding.execution_revision == 0

    execution_mode = TaskExecutionMode(task_id="task_1", mode=ExecutionMode.UNDECIDED)
    assert execution_mode.mode == ExecutionMode.UNDECIDED


def test_summary_notification_and_interruption_models():
    summary = TaskSummary(task_id="task_1", conversational_summary="I am on it.")
    candidate = NotificationCandidate(
        candidate_id="notif_1",
        task_id="task_1",
        candidate_type=NotificationCandidateType.COMPLETED,
        priority=NotificationPriority.P1,
        summary_short="Task completed.",
        created_at="2026-04-06T00:00:00+00:00",
        delivery_status=NotificationDeliveryStatus.PENDING,
        merge_key="completed_digest",
    )
    interruption = Interruption(
        interruption_id="int_1",
        task_id="task_1",
        interruption_type=InterruptionType.SPEECH_ONLY,
        conversational_effect=ConversationEffect.STOP_OUTPUT,
    )
    lease = AssignmentLease(
        task_id="task_1",
        claimed_by="worker_1",
        claim_expires_at="2026-04-06T00:00:00Z",
    )

    assert summary.needs_user_input is False
    assert candidate.priority == NotificationPriority.P1
    assert candidate.candidate_type == NotificationCandidateType.COMPLETED
    assert interruption.interruption_type == InterruptionType.SPEECH_ONLY
    assert lease.claimed_by == "worker_1"
