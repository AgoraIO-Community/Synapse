import json

import pytest

from synapse.blackboard import InMemoryBlackboard
from synapse.communication.context import CommunicationContext, ExecutorRuntimeSummary
from synapse.communication.history import ConversationEntry
from synapse.communication.models.openai import OpenAICommunicationModel
from synapse.communication.tools import build_default_tool_registry
from synapse.communication.tools.base import ToolInputError
from synapse.protocol import Task, TaskStatus


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


class ToolCallingProvider:
    async def run_tool_calling(self, **kwargs):
        result = await kwargs["tool_runner"](
            "create_task",
            {"title": "Check CPU", "goal": "Check CPU usage", "mock_safe": True},
        )
        on_tool_call = kwargs.get("on_tool_call")
        if on_tool_call is not None:
            await on_tool_call(
                {
                    "name": "create_task",
                    "args": {"title": "Check CPU", "goal": "Check CPU usage", "mock_safe": True},
                    "status": "succeeded",
                    "result": result,
                }
            )
        return "Done.", [
            {
                "name": "create_task",
                "args": {"title": "Check CPU", "goal": "Check CPU usage", "mock_safe": True},
                "result": result,
            }
        ]

async def _collect_tool_call(record, bucket):
    bucket.append(record)


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
        focused_task_ids=[],
        focused_tasks=[],
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
    assert "spoken-language friendly" in provider.calls[0]["messages"][2]["content"]
    assert "Do not expose internal tool names" in provider.calls[0]["messages"][3]["content"]
    assert "The latest user message is: Draft email" in provider.calls[0]["messages"][4]["content"]
    assert "Examples:" in provider.calls[0]["messages"][5]["content"]
    assert json.loads(provider.calls[0]["messages"][6]["content"]) == {
        "conversation_id": "conv-1",
        "focused_task_ids": [],
        "focused_tasks": [],
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
    assert provider.calls[0]["messages"][7] == {
        "role": "user",
        "content": "hi",
    }


@pytest.mark.anyio
async def test_openai_model_emits_tool_call_record_for_successful_invocation():
    provider = ToolCallingProvider()
    model = OpenAICommunicationModel(provider)
    tool_calls = []
    context = CommunicationContext(
        conversation_id="conv-1",
        recent_history=[ConversationEntry(role="user", text="hi")],
        tasks=[],
        summaries={},
        focused_task_ids=[],
        focused_tasks=[],
        active_tasks=[],
        recent_tasks=[],
        executor_runtime=ExecutorRuntimeSummary(
            has_real_executor=False,
            available_executor_types=["mock"],
            default_executor_type="mock",
            executors=[],
        ),
        available_tools=["create_task"],
    )
    registry = build_default_tool_registry(InMemoryBlackboard())

    await model.respond(
        user_text="check my pc cpu usage",
        context=context,
        tool_registry=registry,
        on_tool_call=lambda record: _collect_tool_call(record, tool_calls),
    )

    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "create_task"
    assert tool_calls[0].status == "succeeded"
    assert "Check CPU" in (tool_calls[0].result_summary or "")
    assert tool_calls[0].affected_task_ids

@pytest.mark.anyio
async def test_openai_model_blocks_real_executor_request_when_only_mock_is_available():
    provider = GuardExercisingProvider()
    model = OpenAICommunicationModel(provider)
    context = CommunicationContext(
        conversation_id="conv-1",
        recent_history=[ConversationEntry(role="user", text="check my pc cpu usage")],
        tasks=[],
        summaries={},
        focused_task_ids=[],
        focused_tasks=[],
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

    registry = build_default_tool_registry(InMemoryBlackboard())

    with pytest.raises(ToolInputError, match="real executor"):
        await model.respond(
            user_text="check my pc cpu usage",
            context=context,
            tool_registry=registry,
        )
