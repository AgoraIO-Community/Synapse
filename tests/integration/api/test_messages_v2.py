import pytest
from httpx import ASGITransport, AsyncClient

from synopse.api.app import create_app
from synopse.communication.model import CommunicationDecision, ToolCall
from synopse.communication.models import ScriptedCommunicationModel
from synopse.runtime.container import RuntimeContainer


@pytest.mark.anyio
async def test_messages_v2_create_task_and_run_tick():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": CommunicationDecision(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={"title": "Check flights", "goal": "Check flights"},
                        )
                    ],
                )
            }
        )
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

        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        assert len(snapshot["tasks"]) == 1
        assert len(snapshot["execution_runs"]) == 1
