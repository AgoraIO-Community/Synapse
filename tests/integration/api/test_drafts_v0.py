import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.runtime.config import Settings
from synapse.runtime.container import RuntimeContainer
from synapse.communication.models.scripted import ScriptedCommunicationModel, ScriptedPlan


@pytest.mark.anyio
async def test_draft_api_asr_clear_send_freeze():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel({"__default__": ScriptedPlan(reply_override="ok")}),
        settings=Settings(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        response = await client.post(
            f"/api/sessions/{session_id}/draft/asr-turns",
            json={"raw_text": "Make it like ElevenLabs."},
        )
        assert response.status_code == 200
        draft_session = response.json()
        assert draft_session["current_draft"]["goal"]

        response = await client.post(
            f"/api/sessions/{session_id}/draft/asr-turns",
            json={"raw_text": "No, make it like YouMind. Do not add dependencies."},
        )
        draft_session = response.json()
        assert "YouMind" in draft_session["current_draft"]["goal"]
        assert "Do not add dependencies." in draft_session["current_draft"]["constraints"]

        send_response = await client.post(
            f"/api/sessions/{session_id}/draft/send",
            json={"draft_session_id": draft_session["id"]},
        )
        assert send_response.status_code == 200
        task_id = send_response.json()["task_id"]

        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        assert snapshot["draft_session"] is None
        task = next(item for item in snapshot["tasks"] if item["task_id"] == task_id)
        assert task["metadata"]["immutable"] is True
        assert task["metadata"]["source_kind"] == "draft_session"
        assert task["metadata"]["draft_session_id"] == draft_session["id"]
        assert "Do not add dependencies." in task["metadata"]["constraints"]

        response = await client.post(
            f"/api/sessions/{session_id}/draft/asr-turns",
            json={"raw_text": "Actually change the direction."},
        )
        assert response.status_code == 200
        new_draft = response.json()
        assert new_draft["id"] != draft_session["id"]
        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        frozen = next(item for item in snapshot["tasks"] if item["task_id"] == task_id)
        assert frozen["goal"] == task["goal"]


@pytest.mark.anyio
async def test_clear_draft_does_not_remove_tasks():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel({"__default__": ScriptedPlan(reply_override="ok")}),
        settings=Settings(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        draft = (await client.post(
            f"/api/sessions/{session_id}/draft/asr-turns",
            json={"raw_text": "Improve the page."},
        )).json()
        await client.post(f"/api/sessions/{session_id}/draft/send", json={"draft_session_id": draft["id"]})
        draft2 = (await client.post(
            f"/api/sessions/{session_id}/draft/asr-turns",
            json={"raw_text": "Prepare another version."},
        )).json()
        response = await client.post(
            f"/api/sessions/{session_id}/draft/clear",
            json={"draft_session_id": draft2["id"]},
        )
        assert response.status_code == 200
        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        assert snapshot["draft_session"] is None
        assert len(snapshot["tasks"]) == 1
