import asyncio

import pytest
from fastapi import FastAPI, WebSocket
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication.model import ToolCall
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.runtime import build_runtime_container
from synapse.protocol import Task, TaskStatus
from synapse.runtime import Settings
from synapse.runtime.container import RuntimeContainer

from tests.helpers.asgi_websocket import ASGIWebSocketSession


class FakeProvider:
    async def run_tool_calling(self, **kwargs):
        return "OpenAI reply.", []


class ToolCallingProvider:
    async def run_tool_calling(self, **kwargs):
        result = await kwargs["tool_runner"](
            "create_task",
            {"title": "Check flights", "goal": "Check flights", "mock_safe": True},
        )
        on_tool_call = kwargs.get("on_tool_call")
        if on_tool_call is not None:
            await on_tool_call(
                {
                    "name": "create_task",
                    "args": {"title": "Check flights", "goal": "Check flights", "mock_safe": True},
                    "status": "succeeded",
                    "result": result,
                }
            )
        return "OpenAI reply.", [
            {
                "name": "create_task",
                "args": {"title": "Check flights", "goal": "Check flights", "mock_safe": True},
                "result": result,
            }
        ]


class FailedToolCallingProvider:
    async def run_tool_calling(self, **kwargs):
        on_tool_call = kwargs.get("on_tool_call")
        if on_tool_call is not None:
            await on_tool_call(
                {
                    "name": "control_task",
                    "args": {"reference": "email", "command_type": "resume"},
                    "status": "failed",
                    "error": {
                        "code": "invalid_command_type",
                        "message": "Invalid control_task command_type 'resume'.",
                    },
                }
            )
        return "I couldn't resume that because the control command was invalid.", []


async def _receive_until(websocket, predicate, *, limit: int = 12):
    events = []
    for _ in range(limit):
        event = await websocket.receive_json()
        events.append(event)
        if predicate(events):
            return events
    raise AssertionError(f"Timed out waiting for expected websocket events: {events!r}")


@pytest.mark.anyio
async def test_asgi_websocket_harness_receives_minimal_json_messages():
    app = FastAPI()

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({"type": "hello"})
        await websocket.receive_json()
        await websocket.send_json({"type": "bye"})

    async with ASGIWebSocketSession(app, "/ws") as websocket:
        assert (await websocket.receive_json()) == {"type": "hello"}
        await websocket.send_json({"type": "ping"})
        assert (await websocket.receive_json()) == {"type": "bye"}


@pytest.mark.anyio
async def test_session_stream_accepts_message_actions_and_keeps_snapshot_events():
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
                    reply_override="I'll take care of that.",
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

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            await websocket.send_json(
                {
                    "type": "send_message",
                    "request_id": "req-1",
                    "text": "Check flights",
                }
            )

            events = await _receive_until(
                websocket,
                lambda items: any(item["type"] == "assistant_response_completed" for item in items)
                and sum(1 for item in items if item["type"] == "snapshot") >= 2,
            )

        conversation = (await client.get(f"/sessions/{session_id}/conversation")).json()

    event_types = [event["type"] for event in events]
    assert "action_accepted" in event_types
    assert "assistant_response_started" in event_types
    assert "assistant_response_delta" in event_types
    assert "assistant_response_completed" in event_types
    assert "tool_call_started" not in event_types
    assert "tool_call_finished" not in event_types
    assert [event["sequence"] for event in events] == sorted(event["sequence"] for event in events)

    final_snapshot = [event["snapshot"] for event in events if event["type"] == "snapshot"][-1]
    assert len(final_snapshot["tasks"]) == 1
    assert conversation["conversation_history"][-1]["text"] == "I'll take care of that."


@pytest.mark.anyio
async def test_session_stream_emits_conversation_appended_for_notification_messages():
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

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            await session.blackboard.put_task(
                Task(
                    task_id="task-notif",
                    root_task_id="task-notif",
                    title="Blocked task",
                    goal="Blocked task",
                    status=TaskStatus.QUEUED,
                    preferred_executor="mock",
                    metadata={"mock_behavior": "blocked", "mock_block_reason": "Need confirmation."},
                )
            )
            session.schedule_execution()

            events = await _receive_until(
                websocket,
                lambda items: any(item["type"] == "conversation_appended" for item in items),
                limit=20,
            )

    appended = [event for event in events if event["type"] == "conversation_appended"]
    assert appended
    assert appended[-1]["source"] == "notification"
    assert appended[-1]["text"] == "Need confirmation."


@pytest.mark.anyio
async def test_openai_message_flow_logs_summary_llm_diagnostics_without_trace_ui():
    app = create_app()
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=ToolCallingProvider(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            await websocket.send_json(
                {
                    "type": "send_message",
                    "request_id": "req-llm-summary",
                    "text": "what is today's weather",
                }
            )

            events = await _receive_until(
                websocket,
                lambda items: any(item["type"] == "assistant_response_completed" for item in items),
                limit=10,
            )

        diagnostics = (
            await client.get(
                f"/sessions/{session_id}/diagnostics/timeline",
                params={"event_prefix": "comm.llm", "min_level": "INFO"},
            )
        ).json()["events"]

    assert not any(event["type"] == "llm_trace" for event in events)
    assert [event["event_name"] for event in diagnostics] == [
        "comm.llm.request_built",
        "comm.llm.response_completed",
    ]
    assert diagnostics[0]["details"]["phase"] == "request_built"
    assert diagnostics[0]["details"]["message_count"] > 0
    assert "prompt_sections" in diagnostics[0]["details"]
    assert "messages" not in diagnostics[0]["details"]
    assert "user_text" not in diagnostics[0]["details"]
    assert diagnostics[1]["details"]["reply_preview"] == "OpenAI reply."
    assert diagnostics[1]["details"]["tool_invocations"][0]["tool_name"] == "create_task"
    assert "args" not in diagnostics[1]["details"]["tool_invocations"][0]


@pytest.mark.anyio
async def test_openai_message_flow_can_log_verbose_llm_diagnostics_when_enabled():
    app = create_app()
    app.state.runtime_container = build_runtime_container(
        settings=Settings(
            communication_backend="openai",
            openai_api_key="test-key",
            log_llm_details=True,
        ),
        provider=ToolCallingProvider(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "what is today's weather"},
        )

        diagnostics = (
            await client.get(
                f"/sessions/{session_id}/diagnostics/timeline",
                params={"event_prefix": "comm.llm", "min_level": "INFO"},
            )
        ).json()["events"]

    assert diagnostics[0]["details"]["user_text"] == "what is today's weather"
    assert diagnostics[0]["details"]["messages"][0]["role"] == "system"
    assert diagnostics[1]["details"]["reply_text"] == "OpenAI reply."
    assert diagnostics[1]["details"]["tool_invocations"][0]["args"]["title"] == "Check flights"


@pytest.mark.anyio
async def test_session_stream_keeps_tool_calls_out_of_websocket_and_in_diagnostics():
    app = create_app()
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=ToolCallingProvider(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            await websocket.send_json(
                {
                    "type": "send_message",
                    "request_id": "req-tool-call",
                    "text": "what is today's weather",
                }
            )

            events = await _receive_until(
                websocket,
                lambda items: any(item["type"] == "assistant_response_completed" for item in items),
                limit=10,
            )

        diagnostics = (
            await client.get(
                f"/sessions/{session_id}/diagnostics/timeline",
                params={"event_prefix": "comm.tool", "min_level": "INFO"},
            )
        ).json()["events"]

    assert not any(event["type"] == "tool_call" for event in events)
    assert len(diagnostics) == 1
    assert diagnostics[0]["request_id"] == "req-tool-call"
    assert diagnostics[0]["details"]["tool_name"] == "create_task"
    assert diagnostics[0]["outcome"] == "succeeded"
    assert "Check flights" in diagnostics[0]["details"]["result_summary"]


@pytest.mark.anyio
async def test_session_stream_keeps_failed_tool_calls_out_of_websocket_and_in_diagnostics():
    app = create_app()
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=FailedToolCallingProvider(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-email",
                root_task_id="task-email",
                title="Draft email",
                goal="Draft email reply",
            )
        )

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            await websocket.send_json(
                {
                    "type": "send_message",
                    "request_id": "req-failed-tool-call",
                    "text": "Resume the email",
                }
            )

            events = await _receive_until(
                websocket,
                lambda items: any(item["type"] == "assistant_response_completed" for item in items),
                limit=10,
            )

        diagnostics = (
            await client.get(
                f"/sessions/{session_id}/diagnostics/timeline",
                params={"event_prefix": "comm.tool", "min_level": "WARNING"},
            )
        ).json()["events"]

    assert not any(event["type"] == "tool_call" for event in events)
    assert len(diagnostics) == 1
    assert diagnostics[0]["request_id"] == "req-failed-tool-call"
    assert diagnostics[0]["details"]["tool_name"] == "control_task"
    assert diagnostics[0]["outcome"] == "failed"
    assert diagnostics[0]["reason_code"] == "invalid_command_type"


@pytest.mark.anyio
async def test_session_stream_accepts_command_actions_and_returns_snapshot_updates():
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
        await session.blackboard.put_task(
            Task(
                task_id="task-email",
                root_task_id="task-email",
                title="Draft email",
                goal="Draft email",
            )
        )

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            await websocket.send_json(
                {
                    "type": "send_command",
                    "request_id": "req-2",
                    "command_type": "pause_task",
                    "task_id": "task-email",
                }
            )

            events = await _receive_until(
                websocket,
                lambda items: any(item["type"] == "action_accepted" for item in items)
                and any(
                    item["type"] == "snapshot"
                    and item["snapshot"]["tasks"][0]["status"] == "paused"
                    for item in items
                ),
            )

    event_types = [event["type"] for event in events]
    assert "action_accepted" in event_types
    assert "assistant_response_started" not in event_types
    assert "assistant_response_completed" not in event_types
    final_snapshot = [event["snapshot"] for event in events if event["type"] == "snapshot"][-1]
    assert final_snapshot["tasks"][0]["status"] == "paused"


@pytest.mark.anyio
async def test_session_stream_rejects_invalid_command_targets():
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

        async with ASGIWebSocketSession(app, f"/sessions/{session_id}/stream") as websocket:
            initial_event = await websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            await websocket.send_json(
                {
                    "type": "send_command",
                    "request_id": "req-3",
                    "command_type": "pause_task",
                    "task_id": "missing-task",
                }
            )

            rejected_event = (
                await _receive_until(
                    websocket,
                    lambda items: any(item["type"] == "action_rejected" for item in items),
                    limit=4,
                )
            )[-1]

    assert rejected_event["type"] == "action_rejected"
    assert rejected_event["error_code"] == "task_not_found"
