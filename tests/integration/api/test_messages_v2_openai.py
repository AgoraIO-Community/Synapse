import pytest
from httpx import ASGITransport, AsyncClient

from synopse.api.app import create_app
from synopse.runtime import Settings, build_runtime_container


class FakePayload:
    conversational_act = "acknowledge_and_start"
    reply_override = "I'll take care of that."

    def __init__(self):
        self.tool_calls = [
            type(
                "ToolCallPayload",
                (),
                {
                    "name": "create_task",
                    "args": {"title": "Check flights", "goal": "Check flights"},
                },
            )()
        ]


class FakeProvider:
    async def parse_structured(self, **kwargs):
        return FakePayload()


@pytest.mark.anyio
async def test_messages_v2_with_openai_model_mock():
    app = create_app()
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=FakeProvider(),
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
        assert body["reply_text"] == "I'll take care of that."
        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        assert len(snapshot["tasks"]) == 1
