import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synopse.api.app import create_app
from synopse.communication.model import ToolCall
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.runtime import Settings
from synopse.runtime.container import RuntimeContainer


async def _wait_for_timeline_event(client: AsyncClient, session_id: str, predicate, timeout: float = 1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(f"/sessions/{session_id}/diagnostics/timeline")
        body = response.json()
        if predicate(body["events"]):
            return body["events"]
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"Timed out waiting for diagnostic timeline events: {body}")
        await asyncio.sleep(0.01)


@pytest.mark.anyio
async def test_diagnostics_timeline_tracks_message_flow_by_request():
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
        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "hello there"},
        )

        assert response.status_code == 200

        events = await _wait_for_timeline_event(
            client,
            session_id,
            lambda items: any(item["event_name"] == "comm.reply.generated" for item in items),
        )

        request_id = next(
            item["request_id"] for item in events if item["event_name"] == "api.message.accepted"
        )
        response = await client.get(
            f"/sessions/{session_id}/diagnostics/timeline",
            params={"request_id": request_id},
        )
        request_events = response.json()["events"]

    event_names = [item["event_name"] for item in request_events]
    assert "api.message.accepted" in event_names
    assert "comm.message.received" in event_names
    assert "comm.reply.generated" in event_names
    assert all(item["request_id"] == request_id for item in request_events)


@pytest.mark.anyio
async def test_diagnostics_timeline_filters_execution_events_by_task_id():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Check flights",
                                "goal": "Check flights",
                                "mock_safe": True,
                            },
                        )
                    ],
                    reply_override="I'll handle that.",
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
        task_id = response.json()["affected_task_ids"][0]

        events = await _wait_for_timeline_event(
            client,
            session_id,
            lambda items: any(item["event_name"] == "exec.run.completed" for item in items),
        )

        response = await client.get(
            f"/sessions/{session_id}/diagnostics/timeline",
            params={"task_id": task_id},
        )
        task_events = response.json()["events"]

        invalid = await client.get(
            f"/sessions/{session_id}/diagnostics/timeline",
            params={"min_level": "bad-level"},
        )

    event_names = [item["event_name"] for item in task_events]
    assert "bb.task.created" in event_names
    assert "exec.run.started" in event_names
    assert "exec.run.completed" in event_names
    assert any(item["task_id"] == task_id for item in task_events)
    assert invalid.status_code == 400
    assert events


@pytest.mark.anyio
async def test_diagnostics_timeline_request_filter_keeps_blackboard_events_for_message_request():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Check flights",
                                "goal": "Check flights",
                                "mock_safe": True,
                            },
                        )
                    ],
                    reply_override="I'll handle that.",
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

        events = await _wait_for_timeline_event(
            client,
            session_id,
            lambda items: any(item["event_name"] == "bb.task.created" for item in items),
        )
        request_id = next(
            item["request_id"] for item in events if item["event_name"] == "api.message.accepted"
        )

        request_events = (
            await client.get(
                f"/sessions/{session_id}/diagnostics/timeline",
                params={"request_id": request_id},
            )
        ).json()["events"]

    event_names = [item["event_name"] for item in request_events]
    assert "api.message.accepted" in event_names
    assert "comm.tool.called" in event_names
    assert "bb.task.created" in event_names
    assert "bb.mutation.appended" in event_names
    assert all(item["request_id"] == request_id for item in request_events)


@pytest.mark.anyio
async def test_diagnostics_timeline_records_tool_calls_for_scripted_backend():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Check flights",
                                "goal": "Check flights",
                                "mock_safe": True,
                            },
                        )
                    ],
                    reply_override="I'll handle that.",
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

        tool_events = await _wait_for_timeline_event(
            client,
            session_id,
            lambda items: any(item["event_name"] == "comm.tool.called" for item in items),
        )

    event = next(item for item in tool_events if item["event_name"] == "comm.tool.called")
    assert event["details"]["tool_name"] == "create_task"
    assert event["outcome"] == "succeeded"


@pytest.mark.anyio
async def test_diagnostics_timeline_supports_after_sequence_incremental_polling():
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
        initial = (
            await client.get(f"/sessions/{session_id}/diagnostics/timeline")
        ).json()["events"]
        after_sequence = initial[-1]["sequence"]

        await client.post(f"/sessions/{session_id}/messages", json={"text": "hello"})

        events = await _wait_for_timeline_event(
            client,
            session_id,
            lambda items: any(item["event_name"] == "comm.reply.generated" for item in items),
        )
        assert events

        incremental = (
            await client.get(
                f"/sessions/{session_id}/diagnostics/timeline",
                params={"after_sequence": after_sequence},
            )
        ).json()["events"]

    assert incremental
    assert all(item["sequence"] > after_sequence for item in incremental)
