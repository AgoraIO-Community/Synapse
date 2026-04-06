import asyncio

from fastapi.testclient import TestClient

from synopse.api.app import create_app
from synopse.communication.model import ToolCall
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.protocol import Task
from synopse.runtime import Settings
from synopse.runtime.container import RuntimeContainer


def _receive_until(websocket, predicate, *, limit: int = 12):
    events = []
    for _ in range(limit):
        event = websocket.receive_json()
        events.append(event)
        if predicate(events):
            return events
    raise AssertionError(f"Timed out waiting for expected websocket events: {events!r}")


def test_session_stream_accepts_message_actions_and_keeps_snapshot_events():
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

    with TestClient(app) as client:
        session_id = client.post("/sessions").json()["session_id"]

        with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
            initial_event = websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            websocket.send_json(
                {
                    "type": "send_message",
                    "request_id": "req-1",
                    "text": "Check flights",
                }
            )

            events = _receive_until(
                websocket,
                lambda items: any(item["type"] == "assistant_response_completed" for item in items)
                and sum(1 for item in items if item["type"] == "snapshot") >= 2,
            )

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
    assert final_snapshot["conversation_history"][-1]["text"] == "I'll take care of that."


def test_session_stream_accepts_command_actions_and_returns_snapshot_updates():
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

    with TestClient(app) as client:
        session_id = client.post("/sessions").json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        asyncio.run(
            session.blackboard.put_task(
                Task(
                    task_id="task-email",
                    root_task_id="task-email",
                    title="Draft email",
                    goal="Draft email",
                )
            )
        )

        with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
            initial_event = websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            websocket.send_json(
                {
                    "type": "send_command",
                    "request_id": "req-2",
                    "command_type": "pause_task",
                    "task_id": "task-email",
                }
            )

            events = _receive_until(
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


def test_session_stream_rejects_invalid_command_targets():
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

    with TestClient(app) as client:
        session_id = client.post("/sessions").json()["session_id"]

        with client.websocket_connect(f"/sessions/{session_id}/stream") as websocket:
            initial_event = websocket.receive_json()
            assert initial_event["type"] == "snapshot"

            websocket.send_json(
                {
                    "type": "send_command",
                    "request_id": "req-3",
                    "command_type": "pause_task",
                    "task_id": "missing-task",
                }
            )

            rejected_event = _receive_until(
                websocket,
                lambda items: any(item["type"] == "action_rejected" for item in items),
                limit=4,
            )[-1]

    assert rejected_event["type"] == "action_rejected"
    assert rejected_event["error_code"] == "task_not_found"
