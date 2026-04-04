from __future__ import annotations

import asyncio
from types import SimpleNamespace
from pathlib import Path

import pytest

from runtime.infrastructure import config as config_module
from runtime.infrastructure.config import Settings
from runtime.llm.client import LLMServices
from runtime.llm.errors import LLMConfigurationError, LLMInvocationError
from runtime.llm.interpreter_schema import (
    InterpreterAction,
    InterpretationEnvelope,
    InterpreterActionBundle,
    InterpreterRoutingDecision,
    to_runtime_action_bundle,
)
from runtime.llm.message_interpreter import MessageInterpreterClient
from runtime.llm.openai_client import OpenAIProvider
from runtime.llm.prompts import build_response_input
from runtime.llm.prompts import build_response_instructions
from runtime.llm.responder import ResponseClient
from runtime.main import build_services
from runtime.protocols.conversation import ConversationAction, ConversationActionType
from runtime.protocols.runtime import (
    ConversationMode,
    ExecutionTrigger,
    ResolverStrategy,
    RuntimeActionType,
    ScopeOfEffect,
    TargetScope,
)
from runtime.protocols.stream import SessionSnapshot
from runtime.protocols.trace import TraceStage
from runtime.shared_blackboard.trace_state import TraceStateStore
from runtime.protocols.tasks import (
    ControlCommandType,
    Priority,
    TaskReferenceRelation,
    TaskReferenceType,
)


class FakeResponses:
    def __init__(self, parsed=None, text: str | None = None, stream_events=None):
        self._parsed = parsed
        self._text = text
        self._stream_events = stream_events or []

    def parse(self, **kwargs):
        return SimpleNamespace(output_parsed=self._parsed)

    def create(self, **kwargs):
        return SimpleNamespace(output_text=self._text)

    def stream(self, **kwargs):
        return FakeResponseStream(self._stream_events)


class FakeResponseStream:
    def __init__(self, events):
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._events)


class FakeOpenAIClient:
    def __init__(self, parsed=None, text: str | None = None, stream_events=None):
        self.responses = FakeResponses(parsed=parsed, text=text, stream_events=stream_events)


def make_snapshot() -> SessionSnapshot:
    return SessionSnapshot(session_id="session_test")


def make_interpretation(message_id: str) -> InterpretationEnvelope:
    bundle = InterpreterActionBundle(
        bundle_id="bundle_1",
        message_id=message_id,
        actions=[
            InterpreterAction(
                action_id="action_1",
                action_type=RuntimeActionType.CREATE_TASK,
                target_scope=TargetScope.NEW_TASK,
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.HARD,
                scope_of_effect=ScopeOfEffect.TASK,
                title="Search flights",
                goal="Search flights to Tokyo",
            ),
            InterpreterAction(
                action_id="action_2",
                action_type=RuntimeActionType.APPLY_CONTEXT_PATCH,
                target_scope=TargetScope.SESSION,
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.NONE,
                scope_of_effect=ScopeOfEffect.SESSION,
                command_type=ControlCommandType.PAUSE_TASK,
                target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                target_task_reference_relation=TaskReferenceRelation.CURRENT,
                latest_user_goal="Search flights",
            ),
        ],
    )
    decision = InterpreterRoutingDecision(
        decision_id="decision_1",
        message_id=message_id,
        priority_hint=Priority.NORMAL,
        resolver_strategy=ResolverStrategy.IMPLICIT,
    )
    return InterpretationEnvelope(routing_decision=decision, action_bundle=bundle)


def make_clarifying_chat_interpretation(message_id: str) -> InterpretationEnvelope:
    return InterpretationEnvelope(
        routing_decision=InterpreterRoutingDecision(
            decision_id="decision_chat",
            message_id=message_id,
            conversation_mode=ConversationMode.CLARIFICATION,
            needs_clarification=True,
            clarification_reason="User message is ambiguous regarding task actions.",
            priority_hint=Priority.NORMAL,
            resolver_strategy=ResolverStrategy.IMPLICIT,
        ),
        action_bundle=InterpreterActionBundle(
            bundle_id="bundle_chat",
            message_id=message_id,
            actions=[
                InterpreterAction(
                    action_id="action_chat",
                    action_type=RuntimeActionType.APPLY_CONTEXT_PATCH,
                    target_scope=TargetScope.SESSION,
                    priority=Priority.NORMAL,
                    execution_trigger=ExecutionTrigger.NONE,
                    scope_of_effect=ScopeOfEffect.SESSION,
                    command_type=ControlCommandType.PAUSE_TASK,
                    target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                    target_task_reference_relation=TaskReferenceRelation.CURRENT,
                    latest_user_goal="hi",
                )
            ],
        ),
    )


def make_conversation_only_interpretation(
    message_id: str,
    *,
    latest_user_goal: str,
) -> InterpretationEnvelope:
    return InterpretationEnvelope(
        routing_decision=InterpreterRoutingDecision(
            decision_id="decision_conversation",
            message_id=message_id,
            conversation_mode=ConversationMode.CONVERSATION_ONLY,
            needs_clarification=False,
            clarification_reason="",
            priority_hint=Priority.NORMAL,
            resolver_strategy=ResolverStrategy.IMPLICIT,
        ),
        action_bundle=InterpreterActionBundle(
            bundle_id="bundle_conversation",
            message_id=message_id,
            actions=[
                InterpreterAction(
                    action_id="action_conversation",
                    action_type=RuntimeActionType.APPLY_CONTEXT_PATCH,
                    target_scope=TargetScope.SESSION,
                    priority=Priority.NORMAL,
                    execution_trigger=ExecutionTrigger.NONE,
                    scope_of_effect=ScopeOfEffect.SESSION,
                    command_type=ControlCommandType.PAUSE_TASK,
                    target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                    target_task_reference_relation=TaskReferenceRelation.CURRENT,
                    latest_user_goal=latest_user_goal,
                )
            ],
        ),
    )


def test_message_interpreter_fails_fast_without_openai_api_key():
    with pytest.raises(LLMConfigurationError):
        OpenAIProvider(Settings(openai_api_key=None))


def test_message_interpreter_uses_mocked_openai_provider():
    message_id = "message_1"
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(parsed=make_interpretation(message_id)),
    )
    interpreter = MessageInterpreterClient(provider)

    decision, bundle = asyncio.run(
        interpreter.interpret(
            session_id="session_test",
            message_id=message_id,
            text="search flights to tokyo",
            snapshot=make_snapshot(),
        )
    )

    assert decision.message_id == message_id
    assert bundle.message_id == message_id
    assert bundle.actions[0].action_type == RuntimeActionType.CREATE_TASK
    assert bundle.actions[0].payload["input_context"]["requires_executor_capability"] is True


def test_message_interpreter_normalizes_regular_chat_out_of_clarify():
    message_id = "message_chat"
    interpreter = MessageInterpreterClient()

    normalized = interpreter._normalize_interpretation(
        make_clarifying_chat_interpretation(message_id),
        message_id=message_id,
        text="hi",
    )

    decision = normalized.routing_decision
    bundle = normalized.action_bundle
    assert decision.conversation_mode == ConversationMode.CONVERSATION_ONLY
    assert decision.needs_clarification is False
    assert all(action.action_type != RuntimeActionType.CREATE_TASK for action in bundle.actions)


def test_message_interpreter_routes_capability_gated_question_to_task():
    message_id = "message_question"
    interpreter = MessageInterpreterClient()

    normalized = interpreter._normalize_interpretation(
        make_conversation_only_interpretation(
            message_id,
            latest_user_goal="tell me what time is it",
        ),
        message_id=message_id,
        text="tell me what time is it",
    )

    decision = normalized.routing_decision
    bundle = normalized.action_bundle
    assert decision.conversation_mode == ConversationMode.TASK
    assert bundle.actions[0].action_type == RuntimeActionType.CREATE_TASK
    assert bundle.actions[0].goal == "tell me what time is it"
    assert bundle.actions[0].requires_executor_capability is True


def test_interpreter_schema_converts_to_runtime_bundle():
    envelope = make_interpretation("message_1")

    runtime_bundle = to_runtime_action_bundle(envelope.action_bundle)

    assert runtime_bundle.actions[0].action_type == RuntimeActionType.CREATE_TASK
    assert runtime_bundle.actions[0].payload["goal"] == "Search flights to Tokyo"
    assert runtime_bundle.actions[0].payload["input_context"]["requires_executor_capability"] is True
    assert runtime_bundle.actions[1].action_type == RuntimeActionType.APPLY_CONTEXT_PATCH


def test_message_interpreter_rejects_wrong_message_id():
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(parsed=make_interpretation("different_message")),
    )
    interpreter = MessageInterpreterClient(provider)

    with pytest.raises(LLMInvocationError):
        asyncio.run(
            interpreter.interpret(
                session_id="session_test",
                message_id="message_1",
                text="search flights to tokyo",
                snapshot=make_snapshot(),
            )
        )


def test_response_client_uses_mocked_openai_provider():
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(text="I am starting that now."),
    )
    responder = ResponseClient(provider)

    rendered = asyncio.run(
        responder.render(
            ConversationAction(
                action_id="conv_1",
                action_type=ConversationActionType.ACKNOWLEDGE,
            )
        )
    )

    assert rendered == "I am starting that now."


def test_response_client_can_render_chat_reply():
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(text="Hey there."),
    )
    responder = ResponseClient(provider)

    rendered = asyncio.run(
        responder.render(
            ConversationAction(
                action_id="conv_chat",
                action_type=ConversationActionType.CHAT_REPLY,
                metadata={"user_message": "hi"},
            )
        )
    )

    assert rendered == "Hey there."


def test_build_response_input_includes_agent_context():
    action = ConversationAction(
        action_id="conv_1",
        action_type=ConversationActionType.ACKNOWLEDGE,
        metadata={
            "user_message": "tell me what time is it",
            "planned_actions": [{"action_type": "create_task"}],
        },
    )

    rendered_input = build_response_input(action)

    assert '"user_message": "tell me what time is it"' in rendered_input
    assert '"planned_actions"' in rendered_input


def test_build_response_instructions_emphasize_concise_spoken_replies():
    instructions = build_response_instructions()

    assert "spoken aloud" in instructions
    assert "one or two short sentences" in instructions
    assert "Summarize the full task result" in instructions


def test_llm_services_exposes_real_clients_when_configured():
    settings = Settings(openai_api_key="test-key")
    services = LLMServices(
        settings,
        provider=OpenAIProvider(
            settings,
            client=FakeOpenAIClient(
                parsed=make_interpretation("message_1"),
                text="Rendered response",
            ),
        ),
    )

    decision, _ = asyncio.run(
        services.message_interpreter.interpret(
            session_id="session_test",
            message_id="message_1",
            text="search flights",
            snapshot=make_snapshot(),
        )
    )
    rendered = asyncio.run(
        services.responder.render(
            ConversationAction(
                action_id="conv_1",
                action_type=ConversationActionType.ACKNOWLEDGE,
            )
        )
    )

    assert decision.message_id == "message_1"
    assert rendered == "Rendered response"


def test_build_services_fails_without_openai_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SYNOPSE_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", Path("/nonexistent/.env.local"))

    with pytest.raises(LLMConfigurationError):
        build_services()


def test_openai_provider_emits_interpreter_trace_payloads():
    settings = Settings(openai_api_key="test-key")
    trace_store = TraceStateStore()
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(parsed=make_interpretation("message_1")),
    )

    parsed = asyncio.run(
        provider.parse_structured(
            instructions="interpret this",
            input_text='{"message_id":"message_1"}',
            schema=InterpretationEnvelope,
            trace_state_store=trace_store,
            session_id="session_test",
            span_id="span_1",
            related_message_id="message_1",
        )
    )

    snapshot = trace_store.snapshot("session_test")
    assert parsed.routing_decision.message_id == "message_1"
    assert [event.event_type for event in snapshot.recent_traces] == [
        "llm_interpreter_request",
        "llm_interpreter_response",
    ]
    request_payload = snapshot.recent_traces[0].payload
    response_payload = snapshot.recent_traces[1].payload
    assert request_payload["instructions"] == "interpret this"
    assert request_payload["input"] == '{"message_id":"message_1"}'
    assert request_payload["schema_name"] == "InterpretationEnvelope"
    assert "parsed_output" in response_payload
    assert snapshot.recent_traces[0].stage == TraceStage.MESSAGE_INTERPRETER


def test_openai_provider_emits_response_trace_payloads():
    settings = Settings(openai_api_key="test-key")
    trace_store = TraceStateStore()
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(text="Rendered response"),
    )

    output = asyncio.run(
        provider.render_text(
            instructions="reply naturally",
            input_text='{"action_type":"acknowledge"}',
            trace_state_store=trace_store,
            session_id="session_test",
            span_id="span_2",
            related_message_id="message_1",
        )
    )

    snapshot = trace_store.snapshot("session_test")
    assert output == "Rendered response"
    assert [event.event_type for event in snapshot.recent_traces] == [
        "llm_response_request",
        "llm_response_response",
    ]
    request_payload = snapshot.recent_traces[0].payload
    response_payload = snapshot.recent_traces[1].payload
    assert request_payload["instructions"] == "reply naturally"
    assert request_payload["input"] == '{"action_type":"acknowledge"}'
    assert response_payload["output_text"] == "Rendered response"
    assert snapshot.recent_traces[0].stage == TraceStage.RESPONSE_GENERATOR


def test_openai_provider_stream_text_emits_stream_trace_payloads():
    settings = Settings(openai_api_key="test-key")
    trace_store = TraceStateStore()
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(
            stream_events=[
                SimpleNamespace(type="response.output_text.delta", delta="Hello "),
                SimpleNamespace(type="response.output_text.delta", delta="world"),
                SimpleNamespace(type="response.output_text.done", text="Hello world"),
            ]
        ),
    )

    async def collect():
        chunks = []
        async for chunk in provider.stream_text(
            instructions="reply naturally",
            input_text='{"action_type":"chat_reply"}',
            trace_state_store=trace_store,
            session_id="session_test",
            span_id="span_3",
            related_message_id="message_1",
        ):
            chunks.append(chunk)
        return chunks

    output = asyncio.run(collect())

    snapshot = trace_store.snapshot("session_test")
    assert output == ["Hello ", "world"]
    assert [event.event_type for event in snapshot.recent_traces] == [
        "llm_response_stream_request",
        "llm_response_stream_response",
    ]
    assert snapshot.recent_traces[1].payload["output_text"] == "Hello world"
