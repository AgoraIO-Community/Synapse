from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication import persona_pool
from synapse.runtime.container import RuntimeContainer
from synapse.runtime import Settings
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan


def _build_app():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {"__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")}
        ),
        settings=Settings(),
    )
    return app


@pytest.mark.anyio
async def test_session_config_persists_communication_persona_prompt_for_new_sessions(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(persona_pool, "PERSONAS_FILE", tmp_path / "personas.yaml")
    app = _build_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        first_session_id = (await client.post("/sessions")).json()["session_id"]

        response = await client.put(
            f"/sessions/{first_session_id}/config/communication_persona_prompt",
            json={"value": "You are warm and concise."},
        )

        assert response.status_code == 200
        assert (tmp_path / "personas.yaml").exists()
        saved = await client.get(
            f"/sessions/{first_session_id}/config/communication_persona_prompt",
        )
        assert saved.status_code == 200
        assert saved.json()["value"] == "You are warm and concise."

        first_snapshot = (await client.get(f"/sessions/{first_session_id}")).json()
        assert first_snapshot["communication_persona_prompt"] == ""

        second_session_id = (await client.post("/sessions")).json()["session_id"]
        snapshot = (await client.get(f"/sessions/{second_session_id}")).json()

        assert snapshot["communication_persona_prompt"] == "You are warm and concise."
