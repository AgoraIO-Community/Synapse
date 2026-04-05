import asyncio

import pytest

from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.executor_core import ExecutorCapabilities, ExecutorEvent, ExecutorEventType, ExecutorSession
from synopse.protocol import Task, TaskStatus
from synopse.runtime import Settings
from synopse.runtime.session import create_session_runtime


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
    assert published.session_id == "session-1"

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
        if snapshots[-1].execution_runs and snapshots[-1].execution_runs[0].status == "completed":
            break

    assert any(snapshot.execution_runs for snapshot in snapshots)
    assert snapshots[-1].tasks[0].status == "completed"
    session.unsubscribe(queue)
