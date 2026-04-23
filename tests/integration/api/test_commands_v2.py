import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication.model import ToolCall
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.runtime.container import RuntimeContainer
from synapse.runtime import Settings


@pytest.mark.anyio
async def test_commands_v2_pause_task():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={"title": "Draft email", "goal": "Draft email", "mock_safe": True},
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
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        await client.post(f"/api/sessions/{session_id}/messages", json={"text": "Draft email"})
        task_id = (await client.get(f"/api/sessions/{session_id}")).json()["tasks"][0]["task_id"]

        response = await client.post(
            f"/api/sessions/{session_id}/commands",
            json={"command_type": "pause_task", "task_id": task_id},
        )

        assert response.status_code == 200
        deadline = asyncio.get_running_loop().time() + 1.0
        while True:
            snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
            if snapshot["tasks"][0]["status"] == "paused":
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("Timed out waiting for paused task state.")
            await asyncio.sleep(0.01)
        assert snapshot["tasks"][0]["status"] == "paused"
