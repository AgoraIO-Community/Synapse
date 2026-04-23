import json
from types import SimpleNamespace
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.infrastructure.llm import OpenAIProvider
from synapse.protocol import Task
from synapse.runtime import Settings, build_runtime_container


class FakeProvider:
    async def run_tool_calling(self, **kwargs):
        runner = kwargs["tool_runner"]
        result = await runner(
            "create_task",
            {"title": "Check flights", "goal": "Check flights", "mock_safe": True},
        )
        return "I'll take care of that.", [
            {
                "name": "create_task",
                "args": {"title": "Check flights", "goal": "Check flights", "mock_safe": True},
                "result": result,
            }
        ]


def _tool_completion(*, name: str, arguments: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call-1",
                            type="function",
                            function=SimpleNamespace(
                                name=name,
                                arguments=json.dumps(arguments),
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ]
    )


def _text_completion(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=None),
                finish_reason="stop",
            )
        ]
    )


class FakeChatCompletionsAPI:
    def __init__(self, queued_responses: list[SimpleNamespace]) -> None:
        self._queued_responses = list(queued_responses)
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._queued_responses.pop(0)


class FakeClient:
    def __init__(self, queued_responses: list[SimpleNamespace]) -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI(queued_responses))


async def _wait_for_snapshot(client: AsyncClient, session_id: str, predicate, timeout: float = 1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        if predicate(snapshot):
            return snapshot
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected snapshot state.")
        await asyncio.sleep(0.01)


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
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        response = await client.post(
            f"/api/sessions/{session_id}/messages",
            json={"text": "Check flights"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["reply_text"] == "I'll take care of that."
        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        assert len(snapshot["tasks"]) == 1


@pytest.mark.anyio
async def test_messages_v2_invalid_control_task_alias_does_not_500():
    app = create_app()
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=FakeClient(
            [
                _tool_completion(
                    name="control_task",
                    arguments={"reference": "email", "command_type": "resume"},
                ),
                _text_completion(
                    "I couldn't resume that because the control command was invalid.",
                ),
            ]
        ),
    )
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=provider,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-email",
                root_task_id="task-email",
                title="Draft email",
                goal="Draft email reply",
            )
        )

        response = await client.post(
            f"/api/sessions/{session_id}/messages",
            json={"text": "Resume the email"},
        )

        assert response.status_code == 200
        assert response.json()["reply_text"] == (
            "I couldn't resume that because the control command was invalid."
        )

        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        diagnostics = (
            await client.get(
                f"/api/sessions/{session_id}/diagnostics/timeline",
                params={"event_prefix": "bb.command"},
            )
        ).json()
        assert diagnostics["events"] == []
        assert snapshot["tasks"][0]["task_id"] == "task-email"


@pytest.mark.anyio
async def test_messages_v2_follow_up_replays_local_history():
    fake_client = FakeClient(
        [
            _text_completion("First reply."),
            _text_completion("Second reply."),
        ]
    )
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=fake_client,
    )
    app = create_app()
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=provider,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/api/sessions")).json()["session_id"]

        await client.post(f"/api/sessions/{session_id}/messages", json={"text": "hello a1"})
        await client.post(f"/api/sessions/{session_id}/messages", json={"text": "hello a2"})

    first_messages = fake_client.chat.completions.calls[0]["messages"]
    second_messages = fake_client.chat.completions.calls[1]["messages"]

    assert first_messages[-1] == {"role": "user", "content": "hello a1"}
    assert second_messages[-3:] == [
        {"role": "user", "content": "hello a1"},
        {"role": "assistant", "content": "First reply."},
        {"role": "user", "content": "hello a2"},
    ]


@pytest.mark.anyio
async def test_messages_v2_invalid_executor_alias_does_not_persist_bad_task():
    app = create_app()
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=FakeClient(
            [
                _tool_completion(
                    name="create_task",
                    arguments={
                        "title": "Need help",
                        "goal": "Need help",
                        "preferred_executor": "User",
                    },
                ),
                _text_completion("I couldn't start that because the executor choice was invalid."),
            ]
        ),
    )
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=provider,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        response = await client.post(
            f"/api/sessions/{session_id}/messages",
            json={"text": "Do something with executor User"},
        )

        assert response.status_code == 200
        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        assert snapshot["tasks"] == []


@pytest.mark.anyio
async def test_messages_v2_capability_gated_request_is_blocked_when_only_mock_executor_exists():
    app = create_app()
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=FakeClient(
            [
                _tool_completion(
                    name="create_task",
                    arguments={"title": "Check CPU usage", "goal": "Check my PC CPU usage"},
                ),
                _text_completion(
                    "I can't actually check your machine right now because I don't have a real executor connected.",
                ),
            ]
        ),
    )
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=provider,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        response = await client.post(
            f"/api/sessions/{session_id}/messages",
            json={"text": "check my pc cpu usage"},
        )

        assert response.status_code == 200
        assert response.json()["reply_text"] == (
            "I can't actually check your machine right now because I don't have a real executor connected."
        )

        snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
        assert snapshot["tasks"] == []


@pytest.mark.anyio
async def test_messages_v2_preseeded_bad_executor_task_fails_instead_of_500():
    app = create_app()
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=FakeClient([_text_completion("Nothing new.")]),
    )
    app.state.runtime_container = build_runtime_container(
        settings=Settings(communication_backend="openai", openai_api_key="test-key"),
        provider=provider,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-bad",
                root_task_id="task-bad",
                title="Bad executor task",
                goal="Bad executor task",
                preferred_executor="User",
            )
        )

        response = await client.post(
            f"/api/sessions/{session_id}/messages",
            json={"text": "hello"},
        )

        assert response.status_code == 200
        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "failed",
        )
        assert snapshot["tasks"][0]["status"] == "failed"
        assert snapshot["summaries"][0]["latest_user_visible_status"] == "failed"
