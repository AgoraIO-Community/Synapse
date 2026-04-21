import asyncio
import logging

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.executor_core import ExecutorCapabilities, ExecutorEvent, ExecutorEventType, ExecutorSession
from synapse.protocol import Task, TaskStatus
from synapse.runtime import Settings
from synapse.runtime.container import RuntimeContainer


class BlockingExecutor:
    def __init__(self) -> None:
        self._capabilities = ExecutorCapabilities(
            executor_type="blocking",
            supports_follow_up=True,
        )

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="blocking-session", executor_type="blocking")

    async def cancel_run(self, run_id: str) -> None:
        return None

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(self, run, task, session):
        if task.latest_instruction and "approved the pending permission request" in task.latest_instruction:
            yield ExecutorEvent(
                run_id=run.run_id,
                session_id=session.session_id,
                event_type=ExecutorEventType.COMPLETED,
                message="Done after approval.",
            )
            return
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.BLOCKED,
            message="Allow deleting the folder?",
            metadata={"interaction_kind": "permission"},
        )


def _build_app():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")}
        ),
        settings=Settings(),
    )
    return app


async def _wait_for_snapshot(client: AsyncClient, session_id: str, predicate, timeout: float = 4.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        if predicate(snapshot):
            return snapshot
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected snapshot state.")
        await asyncio.sleep(0.05)


@pytest.mark.anyio
async def test_resolve_interaction_request_endpoint_resolves_pending_request():
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(BlockingExecutor())
        await session.blackboard.put_task(
            Task(
                task_id="task-1",
                root_task_id="task-1",
                title="Delete folder",
                goal="Delete folder",
                status=TaskStatus.QUEUED,
                preferred_executor="blocking",
            )
        )
        session.schedule_execution()

        waiting = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["interaction_requests"]) == 1,
        )
        request_id = waiting["interaction_requests"][0]["request_id"]

        response = await client.post(
            f"/sessions/{session_id}/interaction-requests/{request_id}/resolve",
            json={"action": "approve"},
        )
        assert response.status_code == 200

        completed = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "completed",
        )
        assert completed["interaction_requests"][0]["status"] == "approved"


@pytest.mark.anyio
async def test_resolve_interaction_request_returns_404_for_unknown_session():
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/sessions/missing/interaction-requests/ireq-1/resolve",
            json={"action": "approve"},
        )
        assert response.status_code == 404


@pytest.mark.anyio
async def test_resolve_interaction_request_returns_404_for_unknown_request():
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        response = await client.post(
            f"/sessions/{session_id}/interaction-requests/ireq-missing/resolve",
            json={"action": "approve"},
        )
        assert response.status_code == 404


@pytest.mark.anyio
async def test_resolve_interaction_request_returns_409_when_already_resolved():
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(BlockingExecutor())
        await session.blackboard.put_task(
            Task(
                task_id="task-1",
                root_task_id="task-1",
                title="Delete folder",
                goal="Delete folder",
                status=TaskStatus.QUEUED,
                preferred_executor="blocking",
            )
        )
        session.schedule_execution()
        waiting = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["interaction_requests"]) == 1,
        )
        request_id = waiting["interaction_requests"][0]["request_id"]
        first = await client.post(
            f"/sessions/{session_id}/interaction-requests/{request_id}/resolve",
            json={"action": "approve"},
        )
        assert first.status_code == 200
        second = await client.post(
            f"/sessions/{session_id}/interaction-requests/{request_id}/resolve",
            json={"action": "approve"},
        )
        assert second.status_code == 409


@pytest.mark.anyio
async def test_resolve_interaction_request_logs_snapshot_failures(caplog, monkeypatch):
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(BlockingExecutor())
        await session.blackboard.put_task(
            Task(
                task_id="task-log",
                root_task_id="task-log",
                title="Delete folder",
                goal="Delete folder",
                status=TaskStatus.QUEUED,
                preferred_executor="blocking",
            )
        )
        session.schedule_execution()
        waiting = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["interaction_requests"]) == 1,
        )
        request_id = waiting["interaction_requests"][0]["request_id"]

        async def _boom(_self):
            raise RuntimeError("snapshot failed")

        monkeypatch.setattr(type(session), "publish_snapshot", _boom)
        with caplog.at_level(logging.WARNING):
            response = await client.post(
                f"/sessions/{session_id}/interaction-requests/{request_id}/resolve",
                json={"action": "approve"},
            )

        assert response.status_code == 200
        assert "follow-up scheduling failed" in caplog.text
