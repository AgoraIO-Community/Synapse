import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synopse.api.app import create_app
from synopse.communication.model import ToolCall
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.executor_core import ExecutorCapabilities, ExecutorEvent, ExecutorEventType, ExecutorSession
from synopse.runtime.container import RuntimeContainer
from synopse.runtime import Settings
from synopse.protocol import Task, TaskStatus


class SlowExecutor:
    def __init__(self, delay_seconds: float = 0.2) -> None:
        self._delay_seconds = delay_seconds
        self._capabilities = ExecutorCapabilities(executor_type="slow")

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="slow-session", executor_type="slow")

    async def cancel_run(self, run_id: str) -> None:
        return None

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(self, run, task, session):
        await asyncio.sleep(self._delay_seconds)
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.COMPLETED,
            message="slow done",
        )


async def _wait_for_snapshot(client: AsyncClient, session_id: str, predicate, timeout: float = 1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        if predicate(snapshot):
            return snapshot
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected snapshot state.")
        await asyncio.sleep(0.01)


@pytest.mark.anyio
async def test_messages_v2_create_task_and_run_tick():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={"title": "Check flights", "goal": "Check flights"},
                        )
                    ],
                )
            }
        ),
        settings=Settings(),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "Check flights"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["reply_text"]
        assert body["affected_task_ids"]

        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["execution_runs"]) == 1,
        )
        assert len(snapshot["tasks"]) == 1
        assert len(snapshot["execution_runs"]) == 1


@pytest.mark.anyio
async def test_messages_v2_returns_before_background_execution_finishes():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="model_reply",
                    reply_override="Noted.",
                )
            }
        ),
        settings=Settings(),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(SlowExecutor())
        await session.blackboard.put_task(
            Task(
                task_id="task-slow",
                root_task_id="task-slow",
                title="Slow task",
                goal="Slow task",
                status=TaskStatus.QUEUED,
                preferred_executor="slow",
            )
        )

        started = asyncio.get_running_loop().time()
        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "hello"},
        )
        elapsed = asyncio.get_running_loop().time() - started

        assert response.status_code == 200
        assert elapsed < 0.15

        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "completed",
            timeout=1.0,
        )
        assert snapshot["execution_runs"][0]["status"] == "completed"
