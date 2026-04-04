import asyncio
from types import SimpleNamespace

import pytest

from runtime.infrastructure.config import Settings
from runtime.llm.client import LLMServices
from runtime.llm.openai_client import OpenAIProvider
from runtime.main import build_services
from runtime.protocols.conversation import ConversationAction, ConversationActionType


class FakeResponseStream:
    def __init__(self, events):
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._events)


class FakeStreamingResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(output_parsed=None)

    def create(self, **kwargs):
        return SimpleNamespace(output_text="Hello")

    def stream(self, **kwargs):
        return FakeResponseStream(
            [
                SimpleNamespace(type="response.output_text.delta", delta="Hel"),
                SimpleNamespace(type="response.output_text.delta", delta="lo"),
                SimpleNamespace(type="response.output_text.done", text="Hello"),
            ]
        )


class FakeStreamingOpenAIClient:
    def __init__(self):
        self.responses = FakeStreamingResponses()


def build_test_services() -> LLMServices:
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(settings, client=FakeStreamingOpenAIClient())
    return LLMServices(settings, provider=provider)


@pytest.mark.anyio
async def test_emit_conversation_action_streams_transient_chunks_and_persists_final_event():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)
    trace_queue = services.trace_state_store.subscribe(session.session_id)
    action = ConversationAction(
        action_id="conv_1",
        action_type=ConversationActionType.CHAT_REPLY,
        metadata={"user_message": "hi"},
    )

    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        action,
        related_message_id="message_1",
    )

    received = [await asyncio.wait_for(queue.get(), timeout=1) for _ in range(3)]
    event_types = [event.event_type for event in received]
    persisted_event_types = [
        event.event_type
        for event in services.runtime_state_store.get_session(session.session_id).event_log
    ]
    message_history = services.runtime_state_store.get_session(session.session_id).conversation_state[
        "message_history"
    ]

    assert event_types == ["response_chunk", "response_chunk", "chat_reply"]
    assert received[0].payload["render_text"] == "Hel"
    assert received[1].payload["render_text"] == "Hello"
    assert received[2].payload["action"]["render_text"] == "Hello"
    assert persisted_event_types == ["chat_reply"]
    assert len(message_history) == 1
    assert message_history[0]["role"] == "assistant"
    assert message_history[0]["text"] == "Hello"

    trace_payloads: dict[str, dict] = {}
    for _ in range(8):
        trace = await asyncio.wait_for(trace_queue.get(), timeout=1)
        trace_payloads[trace.event_type] = trace.payload
        if trace.event_type == "response_render_completed":
            break

    assert "response_render_completed" in trace_payloads
    llm_response = trace_payloads["response_render_completed"]["llm_response"]
    assert llm_response["output_text"] == "Hello"
    assert llm_response["streamed"] is True
    assert isinstance(llm_response["duration_ms"], int | float)
    assert isinstance(llm_response["ttfb_ms"], int | float)
