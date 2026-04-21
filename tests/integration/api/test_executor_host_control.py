from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.protocol import (
    BindingStatus,
    ExecutionRun,
    ExecutionSession,
    InteractionRequest,
    InteractionRequestKind,
    InteractionRequestStatus,
    RunStatus,
    SessionBinding,
    Task,
    TaskStatus,
)
from synapse.runtime import Settings

from tests.helpers.asgi_websocket import ASGIWebSocketSession


async def _wait_for_snapshot(client: AsyncClient, session_id: str, predicate, timeout: float = 4.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        if predicate(snapshot):
            return snapshot
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected snapshot state.")
        await asyncio.sleep(0.05)


def _build_app():
    return create_app(
        settings=Settings(
            detached_executor_enabled=True,
            executor_host_id="host-1",
            executor_host_token="secret-token",
        )
    )


@pytest.mark.anyio
async def test_detached_executor_waits_for_host_when_unavailable():
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-host-wait",
                root_task_id="task-host-wait",
                title="Hosted task",
                goal="Hosted task",
                status=TaskStatus.QUEUED,
                preferred_executor="codex",
            )
        )
        session.schedule_execution()

        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "waiting_executor",
        )

    assert snapshot["execution_runs"][0]["status"] == "waiting_executor"
    assert snapshot["summaries"][0]["latest_user_visible_status"] == "waiting_executor"
    codex_capability = next(
        capability
        for capability in snapshot["executor_capabilities"]
        if capability["executor_type"] == "codex"
    )
    assert codex_capability["connected"] is False
    assert codex_capability["availability_reason"] == "host_disconnected"


@pytest.mark.anyio
async def test_executor_host_registration_requeues_waiting_task_and_completes():
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-hosted",
                root_task_id="task-hosted",
                title="Hosted task",
                goal="Hosted task",
                status=TaskStatus.QUEUED,
                preferred_executor="codex",
            )
        )
        session.schedule_execution()
        await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "waiting_executor",
        )

        async with ASGIWebSocketSession(app, "/executors/control") as websocket:
            await websocket.send_json(
                {
                    "type": "register_host",
                    "host_id": "host-1",
                    "host_token": "secret-token",
                    "executors": [
                        {
                            "executor_type": "codex",
                            "supports_resume": True,
                            "supports_follow_up": True,
                            "supports_pause": True,
                            "supports_cancel": True,
                        }
                    ],
                }
            )
            ack = await websocket.receive_json()
            assert ack["type"] == "ack"
            dispatch = await websocket.receive_json()
            assert dispatch["type"] == "dispatch_run"
            await websocket.send_json(
                {
                    "type": "run_event",
                    "run_id": dispatch["run_id"],
                    "execution_session_id": dispatch["execution_session_id"],
                    "executor_type": "codex",
                    "session_id": "codex-session-1",
                    "event_type": "progress",
                    "message": "working",
                }
            )
            assert (await websocket.receive_json())["type"] == "ack"
            await websocket.send_json(
                {
                    "type": "run_event",
                    "run_id": dispatch["run_id"],
                    "execution_session_id": dispatch["execution_session_id"],
                    "executor_type": "codex",
                    "session_id": "codex-session-1",
                    "event_type": "completed",
                    "message": "done",
                }
            )
            assert (await websocket.receive_json())["type"] == "ack"
            snapshot = await _wait_for_snapshot(
                client,
                session_id,
                lambda snap: snap["tasks"][0]["status"] == "completed",
            )

    assert snapshot["execution_runs"][-1]["status"] == "completed"
    codex_capability = next(
        capability
        for capability in snapshot["executor_capabilities"]
        if capability["executor_type"] == "codex"
    )
    assert codex_capability["connected"] is True
    assert codex_capability["host_id"] == "host-1"


@pytest.mark.anyio
async def test_resolve_interaction_request_routes_native_response_to_executor_host():
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-native",
                root_task_id="task-native",
                title="Native task",
                goal="Native task",
                status=TaskStatus.WAITING_USER_INPUT,
                preferred_executor="codex",
            )
        )
        await session.blackboard.put_session(
            ExecutionSession(
                execution_session_id="exec-native",
                task_id="task-native",
                base_executor_id="codex",
                executor_host_id="host-1",
                active_run_id="run-native",
                latest_run_id="run-native",
                run_ids=["run-native"],
            )
        )
        await session.blackboard.put_binding(
            SessionBinding(
                task_id="task-native",
                execution_session_id="exec-native",
                executor_host_id="host-1",
                session_id="session-native",
                claimed_by="worker-native",
                claim_expires_at="2026-04-16T00:10:00+00:00",
                binding_status=BindingStatus.ACTIVE,
            )
        )
        await session.blackboard.put_run(
            ExecutionRun(
                run_id="run-native",
                task_id="task-native",
                execution_session_id="exec-native",
                executor_type="codex",
                status=RunStatus.BLOCKED,
                block_reason="Need approval.",
            )
        )
        await session.blackboard.put_interaction_request(
            InteractionRequest(
                request_id="ireq-native",
                task_id="task-native",
                execution_session_id="exec-native",
                run_id="run-native",
                executor_type="codex",
                kind=InteractionRequestKind.PERMISSION,
                status=InteractionRequestStatus.PENDING,
                prompt="Need approval.",
                available_actions=["approve"],
                opaque={
                    "native_response": {
                        "request_id": "req-native",
                        "method": "item/permissions/requestApproval",
                        "params": {"prompt": "Need approval."},
                    }
                },
                created_at="2026-04-06T00:00:00+00:00",
            )
        )

        async with ASGIWebSocketSession(app, "/executors/control") as websocket:
            await websocket.send_json(
                {
                    "type": "register_host",
                    "host_id": "host-1",
                    "host_token": "secret-token",
                    "executors": [
                        {
                            "executor_type": "codex",
                            "supports_resume": True,
                            "supports_follow_up": True,
                            "supports_pause": True,
                            "supports_cancel": True,
                        }
                    ],
                }
            )
            assert (await websocket.receive_json())["type"] == "ack"
            response = await client.post(
                f"/sessions/{session_id}/interaction-requests/ireq-native/resolve",
                json={"action": "approve"},
            )
            assert response.status_code == 200
            command = await websocket.receive_json()

    assert command["type"] == "supply_interaction_response"
    assert command["interaction_request_id"] == "ireq-native"
    assert command["action"] == "approve"
