import json
from types import SimpleNamespace

import pytest

from newbro.communication.tools.base import ToolInputError
from newbro.infrastructure.llm import OpenAIProvider
from newbro.runtime import Settings


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
                message=SimpleNamespace(
                    content=text,
                    tool_calls=None,
                ),
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


class FakeStream:
    def __init__(self, chunks: list[SimpleNamespace]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _stream_chunk(
    *,
    content: str | None = None,
    tool_calls: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ]
    )


def _tool_call_delta(
    *,
    index: int,
    id: str | None = None,
    name: str | None = None,
    arguments: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        index=index,
        id=id,
        type="function",
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


class FakeStreamingChatCompletionsAPI:
    def __init__(self, queued_streams: list[list[SimpleNamespace]]) -> None:
        self._queued_streams = list(queued_streams)
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self._queued_streams.pop(0))


class FakeStreamingClient:
    def __init__(self, queued_streams: list[list[SimpleNamespace]]) -> None:
        self.chat = SimpleNamespace(completions=FakeStreamingChatCompletionsAPI(queued_streams))


async def _collect_tool_call(payload, bucket):
    bucket.append(payload)


@pytest.mark.anyio
async def test_openai_provider_returns_tool_input_errors_as_tool_messages():
    client = FakeClient(
        [
            _tool_completion(
                name="control_task",
                arguments={"reference": "email", "command_type": "resume"},
            ),
            _text_completion("I couldn't resume that because the control command was invalid."),
        ]
    )
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=client,
    )

    async def tool_runner(name: str, args: dict[str, object]) -> object:
        raise ToolInputError(
            f"Invalid control_task command_type '{args['command_type']}'.",
            code="invalid_command_type",
        )

    reply_text, invocations = await provider.run_tool_calling(
        messages=[{"role": "user", "content": "Resume the email task."}],
        tools=[],
        tool_runner=tool_runner,
    )

    assert reply_text == "I couldn't resume that because the control command was invalid."
    assert invocations == []
    second_call_messages = client.chat.completions.calls[1]["messages"]
    assert second_call_messages[1]["role"] == "assistant"
    assert second_call_messages[1]["tool_calls"] == [
        {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "control_task",
                "arguments": '{"reference": "email", "command_type": "resume"}',
            },
        }
    ]
    assert second_call_messages[2] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": json.dumps(
            {
                "error": {
                    "code": "invalid_command_type",
                    "message": "Invalid control_task command_type 'resume'.",
                }
            }
        ),
    }


@pytest.mark.anyio
async def test_openai_provider_emits_tool_call_callback_for_failed_invocation():
    client = FakeClient(
        [
            _tool_completion(
                name="control_task",
                arguments={"reference": "email", "command_type": "resume"},
            ),
            _text_completion("I couldn't resume that because the control command was invalid."),
        ]
    )
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=client,
    )
    tool_calls = []

    async def tool_runner(name: str, args: dict[str, object]) -> object:
        raise ToolInputError(
            f"Invalid control_task command_type '{args['command_type']}'.",
            code="invalid_command_type",
        )

    await provider.run_tool_calling(
        messages=[{"role": "user", "content": "Resume the email task."}],
        tools=[],
        tool_runner=tool_runner,
        on_tool_call=lambda payload: _collect_tool_call(payload, tool_calls),
    )

    assert tool_calls == [
        {
            "name": "control_task",
            "args": {"reference": "email", "command_type": "resume"},
            "status": "failed",
            "error": {
                "code": "invalid_command_type",
                "message": "Invalid control_task command_type 'resume'.",
            },
        }
    ]


@pytest.mark.anyio
async def test_openai_provider_appends_tool_results_before_final_reply():
    client = FakeClient(
        [
            _tool_completion(
                name="list_tasks",
                arguments={"reference": "email"},
            ),
            _text_completion("I found the task you asked about."),
        ]
    )
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=client,
    )

    async def tool_runner(name: str, args: dict[str, object]) -> object:
        return {"tasks": [{"task_id": "task-1"}]}

    reply_text, invocations = await provider.run_tool_calling(
        messages=[{"role": "user", "content": "What tasks mention email?"}],
        tools=[],
        tool_runner=tool_runner,
    )

    assert reply_text == "I found the task you asked about."
    assert invocations == [
        {
            "name": "list_tasks",
            "args": {"reference": "email"},
            "result": {"tasks": [{"task_id": "task-1"}]},
        }
    ]
    assert client.chat.completions.calls[1]["messages"][2] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": json.dumps({"tasks": [{"task_id": "task-1"}]}),
    }


@pytest.mark.anyio
async def test_openai_provider_emits_tool_call_callback_for_successful_invocation():
    client = FakeClient(
        [
            _tool_completion(
                name="list_tasks",
                arguments={"reference": "email"},
            ),
            _text_completion("I found the task you asked about."),
        ]
    )
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=client,
    )
    tool_calls = []

    async def tool_runner(name: str, args: dict[str, object]) -> object:
        return {"tasks": [{"task_id": "task-1"}]}

    await provider.run_tool_calling(
        messages=[{"role": "user", "content": "What tasks mention email?"}],
        tools=[],
        tool_runner=tool_runner,
        on_tool_call=lambda payload: _collect_tool_call(payload, tool_calls),
    )

    assert tool_calls == [
        {
            "name": "list_tasks",
            "args": {"reference": "email"},
            "status": "succeeded",
            "result": {"tasks": [{"task_id": "task-1"}]},
        }
    ]


@pytest.mark.anyio
async def test_openai_provider_streams_only_final_assistant_text_after_tool_calls():
    client = FakeStreamingClient(
        [
            [
                _stream_chunk(content="Let me check that."),
                _stream_chunk(
                    tool_calls=[
                        _tool_call_delta(
                            index=0,
                            id="call-1",
                            name="list_tasks",
                            arguments='{"reference"',
                        )
                    ]
                ),
                _stream_chunk(
                    tool_calls=[
                        _tool_call_delta(
                            index=0,
                            arguments=': "email"}',
                        )
                    ]
                ),
            ],
            [
                _stream_chunk(content="I found "),
                _stream_chunk(content="the task."),
            ],
        ]
    )
    provider = OpenAIProvider(
        Settings(communication_backend="openai", openai_api_key="test-key"),
        client=client,
    )

    streamed_chunks: list[str] = []

    async def tool_runner(name: str, args: dict[str, object]) -> object:
        return {"tasks": [{"task_id": "task-1"}]}

    reply_text, invocations = await provider.run_tool_calling(
        messages=[{"role": "user", "content": "What tasks mention email?"}],
        tools=[],
        tool_runner=tool_runner,
        on_text_delta=streamed_chunks.append,
    )

    assert reply_text == "I found the task."
    assert streamed_chunks == ["I found ", "the task."]
    assert invocations == [
        {
            "name": "list_tasks",
            "args": {"reference": "email"},
            "result": {"tasks": [{"task_id": "task-1"}]},
        }
    ]
    assert client.chat.completions.calls[0]["stream"] is True
