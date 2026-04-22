from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication import persona_pool
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.runtime import Settings
from synapse.runtime.container import RuntimeContainer


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
async def test_persona_changes_apply_only_to_next_session(monkeypatch, tmp_path):
    monkeypatch.setattr(persona_pool, "PERSONAS_FILE", tmp_path / "personas.yaml")
    app = _build_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        first_session_id = (await client.post("/sessions")).json()["session_id"]

        create_response = await client.post(
            f"/sessions/{first_session_id}/personas",
            json={
                "name": "Alex",
                "avatar": "A",
                "base_prompt": "Be direct.",
            },
        )

        assert create_response.status_code == 201
        list_response = await client.get(f"/sessions/{first_session_id}/personas")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        first_snapshot = (await client.get(f"/sessions/{first_session_id}")).json()
        assert first_snapshot["personas"] == []

        second_session_id = (await client.post("/sessions")).json()["session_id"]
        second_snapshot = (await client.get(f"/sessions/{second_session_id}")).json()

        assert len(second_snapshot["personas"]) == 1
        assert second_snapshot["personas"][0]["name"] == "Alex"
