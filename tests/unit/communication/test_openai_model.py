import json

import pytest

from synopse.communication.context import CommunicationContext
from synopse.communication.history import ConversationEntry
from synopse.communication.models.openai import OpenAICommunicationModel
from synopse.protocol import Task, TaskStatus


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def run_tool_calling(self, **kwargs):
        self.calls.append(kwargs)
        return "I'll take care of that.", []


@pytest.mark.anyio
async def test_openai_model_maps_payload_to_model_result():
    provider = FakeProvider()
    model = OpenAICommunicationModel(provider)
    context = CommunicationContext(
        conversation_id="conv-1",
        recent_history=[ConversationEntry(role="user", text="hi")],
        tasks=[
            Task(
                task_id="task_1",
                root_task_id="task_1",
                title="Draft email",
                goal="Draft email",
                status=TaskStatus.CREATED,
            )
        ],
        summaries={},
        available_tools=["create_task"],
    )

    result = await model.respond(
        user_text="Draft email",
        context=context,
        tool_registry=type("DummyRegistry", (), {"openai_tools": []})(),
    )

    assert result.reply_text == "I'll take care of that."
    assert result.conversational_act == "model_reply"
    assert provider.calls[0]["messages"][0]["role"] == "system"
    assert "Communication Brain" in provider.calls[0]["messages"][0]["content"]
    assert json.loads(provider.calls[0]["messages"][1]["content"]) == {
        "conversation_id": "conv-1",
        "tasks": [
            {
                "task_id": "task_1",
                "title": "Draft email",
                "goal": "Draft email",
                "status": "created",
                "priority": 5,
            }
        ],
        "summaries": {},
        "available_tools": ["create_task"],
    }
    assert provider.calls[0]["messages"][2] == {
        "role": "user",
        "content": "hi",
    }
