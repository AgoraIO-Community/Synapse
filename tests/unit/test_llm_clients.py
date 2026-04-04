from __future__ import annotations

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
from runtime.llm.responder import ResponseClient
from runtime.main import build_services
from runtime.protocols.conversation import ConversationAction, ConversationActionType
from runtime.protocols.runtime import (
    ExecutionTrigger,
    ResolverStrategy,
    RuntimeActionType,
    ScopeOfEffect,
    TargetScope,
)
from runtime.protocols.stream import SessionSnapshot
from runtime.protocols.tasks import (
    ControlCommandType,
    Priority,
    TaskReferenceRelation,
    TaskReferenceType,
)


class FakeResponses:
    def __init__(self, parsed=None, text: str | None = None):
        self._parsed = parsed
        self._text = text

    def parse(self, **kwargs):
        return SimpleNamespace(output_parsed=self._parsed)

    def create(self, **kwargs):
        return SimpleNamespace(output_text=self._text)


class FakeOpenAIClient:
    def __init__(self, parsed=None, text: str | None = None):
        self.responses = FakeResponses(parsed=parsed, text=text)


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

    decision, bundle = interpreter.interpret(
        session_id="session_test",
        message_id=message_id,
        text="search flights to tokyo",
        snapshot=make_snapshot(),
    )

    assert decision.message_id == message_id
    assert bundle.message_id == message_id
    assert bundle.actions[0].action_type == RuntimeActionType.CREATE_TASK


def test_interpreter_schema_converts_to_runtime_bundle():
    envelope = make_interpretation("message_1")

    runtime_bundle = to_runtime_action_bundle(envelope.action_bundle)

    assert runtime_bundle.actions[0].action_type == RuntimeActionType.CREATE_TASK
    assert runtime_bundle.actions[0].payload["goal"] == "Search flights to Tokyo"
    assert runtime_bundle.actions[1].action_type == RuntimeActionType.APPLY_CONTEXT_PATCH


def test_message_interpreter_rejects_wrong_message_id():
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(parsed=make_interpretation("different_message")),
    )
    interpreter = MessageInterpreterClient(provider)

    with pytest.raises(LLMInvocationError):
        interpreter.interpret(
            session_id="session_test",
            message_id="message_1",
            text="search flights to tokyo",
            snapshot=make_snapshot(),
        )


def test_response_client_uses_mocked_openai_provider():
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(text="I am starting that now."),
    )
    responder = ResponseClient(provider)

    rendered = responder.render(
        ConversationAction(
            action_id="conv_1",
            action_type=ConversationActionType.ACKNOWLEDGE,
        )
    )

    assert rendered == "I am starting that now."


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

    decision, _ = services.message_interpreter.interpret(
        session_id="session_test",
        message_id="message_1",
        text="search flights",
        snapshot=make_snapshot(),
    )
    rendered = services.responder.render(
        ConversationAction(
            action_id="conv_1",
            action_type=ConversationActionType.ACKNOWLEDGE,
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
