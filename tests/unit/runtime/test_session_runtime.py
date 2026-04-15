import asyncio

import pytest

from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.protocol import (
    BindingStatus,
    ExecutionMode,
    ExecutionRun,
    ExecutionSession as RuntimeExecutionSession,
    NotificationCandidate,
    NotificationCandidateType,
    NotificationDeliveryStatus,
    NotificationPriority,
    RunStatus,
    SessionBinding,
    TaskCommand,
    TaskCommandType,
    TaskExecutionMode,
)
from synapse.executor_core import ExecutorCapabilities, ExecutorEvent, ExecutorEventType, ExecutorSession
from synapse.protocol import Task, TaskStatus
from synapse.runtime import Settings
from synapse.runtime.session import create_session_runtime


@pytest.mark.anyio
async def test_session_runtime_publish_snapshot_notifies_subscribers():
    session = create_session_runtime(
        "session-1",
        model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="request_clarification")}
        ),
        settings=Settings(),
    )
    queue = session.subscribe()

    snapshot = await session.publish_snapshot()
    published = await queue.get()

    assert snapshot.session_id == "session-1"
    assert published.type == "snapshot"
    assert published.snapshot.session_id == "session-1"

    session.unsubscribe(queue)


@pytest.mark.anyio
async def test_session_runtime_registers_codex_when_enabled(tmp_path):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n")
    fake_codex.chmod(0o755)

    session = create_session_runtime(
        "session-2",
        model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="request_clarification")}
        ),
        settings=Settings(codex_executor_enabled=True, codex_command=str(fake_codex)),
    )

    assert sorted(session.registry.list_executor_types()) == ["codex", "mock"]


class BackgroundTestExecutor:
    def __init__(self) -> None:
        self._capabilities = ExecutorCapabilities(executor_type="background")

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="background-session", executor_type="background")

    async def cancel_run(self, run_id: str) -> None:
        return None

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(self, run, task, session):
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.PROGRESS,
            message="working",
        )
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.COMPLETED,
            message="done",
        )


class CancelTrackingExecutor:
    def __init__(self) -> None:
        self._capabilities = ExecutorCapabilities(executor_type="cancellable", supports_cancel=True)
        self.cancelled_runs: list[str] = []

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="cancellable-session", executor_type="cancellable")

    async def cancel_run(self, run_id: str) -> None:
        self.cancelled_runs.append(run_id)

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(self, run, task, session):
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.PROGRESS,
            message="working",
        )


@pytest.mark.anyio
async def test_session_runtime_snapshot_pump_publishes_background_execution_updates():
    session = create_session_runtime(
        "session-3",
        model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="request_clarification")}
        ),
        settings=Settings(),
    )
    session.registry.register(BackgroundTestExecutor())
    queue = session.subscribe()
    await session.blackboard.put_task(
        Task(
            task_id="task-bg",
            root_task_id="task-bg",
            title="Background task",
            goal="Background task",
            status=TaskStatus.QUEUED,
            preferred_executor="background",
        )
    )
    session.schedule_execution()

    snapshots = []
    for _ in range(3):
        snapshots.append(await asyncio.wait_for(queue.get(), timeout=1.0))
        if (
            snapshots[-1].type == "snapshot"
            and snapshots[-1].snapshot.execution_runs
            and snapshots[-1].snapshot.execution_runs[0].status == "completed"
        ):
            break

    snapshot_payloads = [event.snapshot for event in snapshots if event.type == "snapshot"]
    assert any(snapshot.execution_runs for snapshot in snapshot_payloads)
    assert snapshot_payloads[-1].tasks[0].status == "completed"
    session.unsubscribe(queue)


@pytest.mark.anyio
async def test_session_runtime_snapshot_includes_execution_modes():
    session = create_session_runtime(
        "session-4",
        model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="request_clarification")}
        ),
        settings=Settings(),
    )
    await session.blackboard.put_execution_mode(
        TaskExecutionMode(
            task_id="task-1",
            mode=ExecutionMode.MANAGED,
            decided_from_run_id="run-1",
            elapsed_seconds=32.0,
        )
    )

    snapshot = await session.snapshot()

    assert snapshot.execution_modes[0].mode == ExecutionMode.MANAGED


@pytest.mark.anyio
async def test_session_runtime_snapshot_includes_notification_candidates():
    session = create_session_runtime(
        "session-5",
        model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="request_clarification")}
        ),
        settings=Settings(),
    )
    await session.blackboard.put_notification_candidate(
        NotificationCandidate(
            candidate_id="notif-1",
            task_id="task-1",
            candidate_type=NotificationCandidateType.COMPLETED,
            priority=NotificationPriority.P2,
            summary_short="Task completed.",
            created_at="2026-04-06T00:00:00+00:00",
            delivery_status=NotificationDeliveryStatus.PENDING,
            merge_key="completed_digest",
        )
    )

    snapshot = await session.snapshot()

    assert snapshot.notification_candidates[0].candidate_id == "notif-1"


@pytest.mark.anyio
async def test_session_runtime_apply_command_cancels_live_run_and_suppresses_pending_notifications():
    session = create_session_runtime(
        "session-6",
        model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="request_clarification")}
        ),
        settings=Settings(),
    )
    executor = CancelTrackingExecutor()
    session.registry.register(executor)
    await session.blackboard.put_task(
        Task(
            task_id="task-cancel",
            root_task_id="task-cancel",
            title="Cancelable task",
            goal="Cancelable task",
            status=TaskStatus.RUNNING,
            preferred_executor="cancellable",
        )
    )
    await session.blackboard.put_session(
        RuntimeExecutionSession(
            execution_session_id="exec-session-cancel",
            task_id="task-cancel",
            base_executor_id="cancellable",
            active_run_id="run-cancel",
            latest_run_id="run-cancel",
            run_ids=["run-cancel"],
        )
    )
    await session.blackboard.put_binding(
        SessionBinding(
            task_id="task-cancel",
            execution_session_id="exec-session-cancel",
            session_id="cancellable-session",
            claimed_by="worker-session-6",
            claim_expires_at="2026-04-16T00:10:00+00:00",
            binding_status=BindingStatus.ACTIVE,
        )
    )
    await session.blackboard.put_run(
        ExecutionRun(
            run_id="run-cancel",
            task_id="task-cancel",
            execution_session_id="exec-session-cancel",
            executor_type="cancellable",
            status=RunStatus.RUNNING,
        )
    )
    await session.blackboard.put_notification_candidate(
        NotificationCandidate(
            candidate_id="notif-cancel",
            task_id="task-cancel",
            candidate_type=NotificationCandidateType.COMPLETED,
            priority=NotificationPriority.P2,
            summary_short="Should not emit.",
            created_at="2026-04-16T00:00:00+00:00",
            delivery_status=NotificationDeliveryStatus.PENDING,
            merge_key="completed_digest",
        )
    )

    await session.apply_command(
        TaskCommand(
            command_id="cmd-cancel",
            task_id="task-cancel",
            command_type=TaskCommandType.CANCEL_TASK,
            created_by="test",
        )
    )

    task = await session.blackboard.get_task("task-cancel")
    run = await session.blackboard.get_run("run-cancel")
    execution_session = await session.blackboard.get_session("exec-session-cancel")
    binding = await session.blackboard.get_binding("task-cancel")
    summary = await session.blackboard.get_summary("task-cancel")
    candidate = await session.blackboard.get_notification_candidate("notif-cancel")

    assert executor.cancelled_runs == ["run-cancel"]
    assert task is not None and task.status == TaskStatus.CANCELLED
    assert run is not None and run.status == RunStatus.CANCELLED
    assert execution_session is not None and execution_session.active_run_id is None
    assert binding is not None and binding.binding_status == BindingStatus.RELEASED
    assert summary is not None and summary.latest_user_visible_status == "cancelled"
    assert candidate is not None and candidate.delivery_status == NotificationDeliveryStatus.SUPPRESSED
