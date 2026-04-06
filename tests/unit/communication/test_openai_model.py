import json

import pytest

from synopse.communication.context import CommunicationContext, ExecutorRuntimeSummary
from synopse.communication.history import ConversationEntry
from synopse.communication.models.openai import OpenAICommunicationModel
from synopse.communication.tools.base import ToolInputError
from synopse.protocol import Task, TaskStatus


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def run_tool_calling(self, **kwargs):
        self.calls.append(kwargs)
        return "I'll take care of that.", []


class GuardExercisingProvider:
    async def run_tool_calling(self, **kwargs):
        return "blocked", [
            {
                "name": "create_task",
                "args": {"title": "Check CPU", "goal": "Check CPU usage"},
                "result": await kwargs["tool_runner"](
                    "create_task",
                    {"title": "Check CPU", "goal": "Check CPU usage"},
                ),
            }
        ]


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
        active_tasks=[],
        recent_tasks=[],
        executor_runtime=ExecutorRuntimeSummary(
            has_real_executor=False,
            available_executor_types=[],
            default_executor_type=None,
            executors=[],
        ),
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
    assert "Tool-selection policy" in provider.calls[0]["messages"][1]["content"]
    assert "Examples:" in provider.calls[0]["messages"][2]["content"]
    assert json.loads(provider.calls[0]["messages"][3]["content"]) == {
        "conversation_id": "conv-1",
        "active_tasks": [],
        "recent_tasks": [],
        "executor_runtime": {
            "has_real_executor": False,
            "available_executor_types": [],
            "default_executor_type": None,
            "executors": [],
        },
        "available_tools": ["create_task"],
    }
    assert provider.calls[0]["messages"][4] == {
        "role": "user",
        "content": "hi",
    }


@pytest.mark.anyio
async def test_openai_model_blocks_real_executor_request_when_only_mock_is_available():
    provider = GuardExercisingProvider()
    model = OpenAICommunicationModel(provider)
    context = CommunicationContext(
        conversation_id="conv-1",
        recent_history=[ConversationEntry(role="user", text="check my pc cpu usage")],
        tasks=[],
        summaries={},
        active_tasks=[],
        recent_tasks=[],
        executor_runtime=ExecutorRuntimeSummary(
            has_real_executor=False,
            available_executor_types=["mock"],
            default_executor_type="mock",
            executors=[
                {
                    "executor_type": "mock",
                    "is_mock": True,
                    "supports_follow_up": True,
                    "supports_resume": False,
                    "supports_pause": True,
                    "supports_cancel": True,
                    "supports_setup": False,
                }
            ],
        ),
        available_tools=["create_task"],
    )

    class DummyToolSpec:
        async def invoke(self, **kwargs):
            return kwargs

    class DummyRegistry:
        openai_tools = []

        @staticmethod
        def get(name: str):
            return DummyToolSpec()

    with pytest.raises(ToolInputError, match="real executor"):
        await model.respond(
            user_text="check my pc cpu usage",
            context=context,
            tool_registry=DummyRegistry(),
        )
