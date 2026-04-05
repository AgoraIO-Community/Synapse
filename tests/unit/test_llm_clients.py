from __future__ import annotations

import asyncio
from types import SimpleNamespace
from pathlib import Path

import pytest
from pydantic import ValidationError

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
from runtime.llm.prompts import (
    build_interpreter_input,
    build_interpreter_instructions,
    build_response_input,
    build_response_instructions,
    INTERPRETER_PROMPT_CACHE_KEY,
)
from runtime.llm.responder import ResponseClient
from runtime.main import build_services
from runtime.protocols.conversation import ConversationAction, ConversationActionType
from runtime.protocols.execution import ExecutorCapability
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
    Task,
    TaskReferenceRelation,
    TaskReferenceType,
    TaskStatus,
)


class FakeResponses:
    def __init__(self, parsed=None, text: str | None = None, stream_events=None):
        self._parsed = parsed
        self._text = text
        self._stream_events = stream_events or []
        self.last_parse_kwargs: dict | None = None
        self.last_create_kwargs: dict | None = None

    def parse(self, **kwargs):
        self.last_parse_kwargs = kwargs
        return SimpleNamespace(output_parsed=self._parsed)

    def create(self, **kwargs):
        self.last_create_kwargs = kwargs
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


class FakeOpenAIClientWithoutStream:
    def __init__(self, text: str | None = None):
        self.responses = SimpleNamespace(create=lambda **kwargs: SimpleNamespace(output_text=text))


class FailingResponses:
    def __init__(self, *, parse_error: Exception | None = None, create_error: Exception | None = None):
        self._parse_error = parse_error
        self._create_error = create_error

    def parse(self, **kwargs):
        assert self._parse_error is not None
        raise self._parse_error

    def create(self, **kwargs):
        assert self._create_error is not None
        raise self._create_error


class FailingOpenAIClient:
    def __init__(self, *, parse_error: Exception | None = None, create_error: Exception | None = None):
        self.responses = FailingResponses(parse_error=parse_error, create_error=create_error)


def assert_duration_ms(payload: dict) -> None:
    assert "duration_ms" in payload
    assert isinstance(payload["duration_ms"], int | float)
    assert payload["duration_ms"] >= 0


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


def test_message_interpreter_preserves_model_conversation_only_output():
    message_id = "message_chat"
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(
            parsed=make_conversation_only_interpretation(
                message_id,
                latest_user_goal="hi",
            )
        ),
    )
    interpreter = MessageInterpreterClient(provider)

    decision, bundle = asyncio.run(
        interpreter.interpret(
            session_id="session_test",
            message_id=message_id,
            text="hi",
            snapshot=make_snapshot(),
        )
    )

    assert decision.conversation_mode == ConversationMode.CONVERSATION_ONLY
    assert len(bundle.actions) == 1
    assert bundle.actions[0].action_type == RuntimeActionType.APPLY_CONTEXT_PATCH


def test_message_interpreter_preserves_model_task_output():
    message_id = "message_question"
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
            text="tell me what time is it",
            snapshot=make_snapshot(),
        )
    )

    assert decision.conversation_mode == ConversationMode.TASK
    assert bundle.actions[0].action_type == RuntimeActionType.CREATE_TASK
    assert bundle.actions[0].payload["goal"] == "Search flights to Tokyo"


def test_message_interpreter_does_not_synthesize_task_from_model_conversation_only():
    message_id = "message_social_followup"
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(
            parsed=make_conversation_only_interpretation(
                message_id,
                latest_user_goal="btw how are you doing recently",
            )
        ),
    )
    interpreter = MessageInterpreterClient(provider)

    decision, bundle = asyncio.run(
        interpreter.interpret(
            session_id="session_test",
            message_id=message_id,
            text="btw how are you doing recently",
            snapshot=make_snapshot(),
        )
    )

    assert decision.conversation_mode == ConversationMode.CONVERSATION_ONLY
    assert all(action.action_type != RuntimeActionType.CREATE_TASK for action in bundle.actions)


def test_interpreter_schema_converts_to_runtime_bundle():
    envelope = make_interpretation("message_1")

    runtime_bundle = to_runtime_action_bundle(envelope.action_bundle)

    assert runtime_bundle.actions[0].action_type == RuntimeActionType.CREATE_TASK
    assert runtime_bundle.actions[0].payload["goal"] == "Search flights to Tokyo"
    assert runtime_bundle.actions[0].payload["input_context"]["requires_executor_capability"] is True
    assert runtime_bundle.actions[1].action_type == RuntimeActionType.APPLY_CONTEXT_PATCH


def test_interpreter_schema_derives_create_task_title_from_goal():
    bundle = InterpreterActionBundle(
        bundle_id="bundle_derive_title",
        message_id="message_derive_title",
        actions=[
            InterpreterAction(
                action_id="action_1",
                action_type=RuntimeActionType.CREATE_TASK,
                target_scope=TargetScope.NEW_TASK,
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.HARD,
                scope_of_effect=ScopeOfEffect.TASK,
                goal="Check today's weather",
            )
        ],
    )

    runtime_bundle = to_runtime_action_bundle(bundle)

    assert runtime_bundle.actions[0].payload["goal"] == "Check today's weather"
    assert runtime_bundle.actions[0].payload["title"] == "Check today's weather"


def test_interpreter_schema_rejects_create_task_without_goal():
    with pytest.raises(ValidationError, match="create_task requires a non-empty goal"):
        InterpreterAction(
            action_id="action_missing_goal",
            action_type=RuntimeActionType.CREATE_TASK,
            target_scope=TargetScope.NEW_TASK,
            priority=Priority.NORMAL,
            execution_trigger=ExecutionTrigger.HARD,
            scope_of_effect=ScopeOfEffect.TASK,
            goal="   ",
        )


def test_interpreter_schema_rejects_whitespace_only_create_task_title():
    with pytest.raises(
        ValidationError, match="create_task title must be non-empty when provided"
    ):
        InterpreterAction(
            action_id="action_bad_title",
            action_type=RuntimeActionType.CREATE_TASK,
            target_scope=TargetScope.NEW_TASK,
            priority=Priority.NORMAL,
            execution_trigger=ExecutionTrigger.HARD,
            scope_of_effect=ScopeOfEffect.TASK,
            title="   ",
            goal="Check today's weather",
        )


def test_interpreter_schema_rejects_update_task_without_goal():
    with pytest.raises(ValidationError, match="update_task requires a non-empty goal"):
        InterpreterAction(
            action_id="action_missing_update_goal",
            action_type=RuntimeActionType.UPDATE_TASK,
            target_scope=TargetScope.EXISTING_TASK,
            priority=Priority.NORMAL,
            execution_trigger=ExecutionTrigger.SOFT,
            scope_of_effect=ScopeOfEffect.TASK,
            target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
            latest_instruction="continue with recipient info",
            goal="   ",
        )


def test_interpreter_schema_derives_update_task_title_from_goal():
    bundle = InterpreterActionBundle(
        bundle_id="bundle_update_title",
        message_id="message_update_title",
        actions=[
            InterpreterAction(
                action_id="action_update_1",
                action_type=RuntimeActionType.UPDATE_TASK,
                target_scope=TargetScope.EXISTING_TASK,
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.SOFT,
                scope_of_effect=ScopeOfEffect.TASK,
                target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                goal="Continue with the recipient info",
                latest_instruction="Continue with the recipient info",
            )
        ],
    )

    runtime_bundle = to_runtime_action_bundle(bundle)

    assert runtime_bundle.actions[0].payload["goal"] == "Continue with the recipient info"
    assert (
        runtime_bundle.actions[0].payload["title"]
        == "Continue with the recipient info"
    )
    assert (
        runtime_bundle.actions[0].payload["latest_instruction"]
        == "Continue with the recipient info"
    )


def test_interpretation_envelope_schema_avoids_one_of():
    schema_json = InterpretationEnvelope.model_json_schema()

    assert "oneOf" not in str(schema_json)


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


def test_message_interpreter_rejects_invalid_create_task_payload_from_model():
    invalid_envelope = InterpretationEnvelope.model_construct(
        routing_decision=InterpreterRoutingDecision.model_construct(
            decision_id="decision_invalid",
            message_id="message_invalid",
            conversation_mode=ConversationMode.TASK,
            needs_clarification=False,
            clarification_reason=None,
            priority_hint=Priority.NORMAL,
            resolver_strategy=ResolverStrategy.IMPLICIT,
        ),
        action_bundle=InterpreterActionBundle.model_construct(
            bundle_id="bundle_invalid",
            message_id="message_invalid",
            actions=[
                InterpreterAction.model_construct(
                    action_id="action_invalid",
                    action_type=RuntimeActionType.CREATE_TASK,
                    target_scope=TargetScope.NEW_TASK,
                    priority=Priority.NORMAL,
                    execution_trigger=ExecutionTrigger.HARD,
                    scope_of_effect=ScopeOfEffect.TASK,
                    title=None,
                    goal=None,
                    latest_instruction=None,
                )
            ],
        ),
    )
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(parsed=invalid_envelope),
    )
    interpreter = MessageInterpreterClient(provider)

    with pytest.raises(
        LLMInvocationError,
        match="Interpreter returned invalid runtime action payload: create_task requires a non-empty goal",
    ):
        asyncio.run(
            interpreter.interpret(
                session_id="session_test",
                message_id="message_invalid",
                text="what is today's weather",
                snapshot=make_snapshot(),
            )
        )


def test_message_interpreter_rejects_invalid_update_task_payload_from_model():
    invalid_envelope = InterpretationEnvelope.model_construct(
        routing_decision=InterpreterRoutingDecision.model_construct(
            decision_id="decision_invalid_update",
            message_id="message_invalid_update",
            conversation_mode=ConversationMode.TASK,
            needs_clarification=False,
            clarification_reason=None,
            priority_hint=Priority.NORMAL,
            resolver_strategy=ResolverStrategy.IMPLICIT,
        ),
        action_bundle=InterpreterActionBundle.model_construct(
            bundle_id="bundle_invalid_update",
            message_id="message_invalid_update",
            actions=[
                InterpreterAction.model_construct(
                    action_id="action_invalid_update",
                    action_type=RuntimeActionType.UPDATE_TASK,
                    target_scope=TargetScope.EXISTING_TASK,
                    priority=Priority.NORMAL,
                    execution_trigger=ExecutionTrigger.SOFT,
                    scope_of_effect=ScopeOfEffect.TASK,
                    target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                    title=None,
                    goal=None,
                    latest_instruction="i'm in shanghai",
                )
            ],
        ),
    )
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClient(parsed=invalid_envelope),
    )
    interpreter = MessageInterpreterClient(provider)

    with pytest.raises(
        LLMInvocationError,
        match="Interpreter returned invalid runtime action payload: update_task requires a non-empty goal",
    ):
        asyncio.run(
            interpreter.interpret(
                session_id="session_test",
                message_id="message_invalid_update",
                text="i'm in shanghai",
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


def test_build_interpreter_input_includes_message_history():
    snapshot = SessionSnapshot(
        session_id="session_test",
        conversation_state={
            "message_history": [
                {"role": "user", "text": f"message-{index}", "message_id": f"m{index}"}
                for index in range(12)
            ]
        },
    )

    rendered_input = build_interpreter_input(
        message_id="message_1",
        text="what now?",
        snapshot=snapshot,
    )

    assert '"message_history"' in rendered_input
    assert '"text": "message-11"' in rendered_input
    assert '"text": "message-2"' in rendered_input
    assert '"text": "message-1"' not in rendered_input


def test_build_interpreter_input_uses_compact_runtime_context():
    snapshot = SessionSnapshot(
        session_id="session_test",
        conversation_state={
            "message_history": [
                {"role": "user", "text": "hello", "message_id": "m1"},
            ]
        },
        pending_clarifications=[
            ConversationAction(
                action_id="conv_1",
                action_type=ConversationActionType.CLARIFY,
                target_task_id="task_active",
                reason="Need recipient info",
            )
        ],
        executor_capabilities=[
            ExecutorCapability(
                executor_id="codex_executor",
                label="Codex Executor",
                capability_tags=["coding"],
                supports_cancel=True,
                supports_streaming=True,
            )
        ],
        task_registry=[
            Task(
                task_id="task_active_1",
                root_task_id="task_active_1",
                title="Weather",
                goal="Get today's weather in Shanghai",
                status=TaskStatus.RUNNING,
            ),
            Task(
                task_id="task_done_1",
                root_task_id="task_done_1",
                title="CPU",
                goal="Check CPU usage",
                status=TaskStatus.DONE,
            ),
        ],
    )

    rendered_input = build_interpreter_input(
        message_id="message_1",
        text="continue with the recipient info",
        snapshot=snapshot,
    )

    assert '"pending_clarifications"' in rendered_input
    assert '"Need recipient info"' in rendered_input
    assert '"active_tasks"' in rendered_input
    assert '"task_id": "task_active_1"' in rendered_input
    assert '"goal": "Get today\'s weather in Shanghai"' in rendered_input
    assert '"task_id": "task_done_1"' not in rendered_input
    assert '"title": "Weather"' not in rendered_input
    assert '"status": "running"' not in rendered_input
    assert '"executor_capabilities"' in rendered_input
    assert '"executor_id": "codex_executor"' in rendered_input
    assert '"session_snapshot"' not in rendered_input


def test_build_interpreter_input_only_includes_active_tasks_with_id_and_goal():
    snapshot = SessionSnapshot(
        session_id="session_test",
        task_registry=[
            Task(
                task_id="task_queued",
                root_task_id="task_queued",
                title="Queued weather",
                goal="Get weather in Shanghai",
                status=TaskStatus.QUEUED,
            ),
            Task(
                task_id="task_running",
                root_task_id="task_running",
                title="Running weather",
                goal="Get weather in Beijing",
                status=TaskStatus.RUNNING,
            ),
            Task(
                task_id="task_blocked",
                root_task_id="task_blocked",
                title="Blocked weather",
                goal="Get weather in Shenzhen",
                status=TaskStatus.BLOCKED,
            ),
            Task(
                task_id="task_done",
                root_task_id="task_done",
                title="Done weather",
                goal="Get weather in Guangzhou",
                status=TaskStatus.DONE,
            ),
            Task(
                task_id="task_failed",
                root_task_id="task_failed",
                title="Failed weather",
                goal="Get weather in Hangzhou",
                status=TaskStatus.FAILED,
            ),
        ],
    )

    rendered_input = build_interpreter_input(
        message_id="message_1",
        text="i'm in shanghai",
        snapshot=snapshot,
    )

    assert '"task_id": "task_queued"' in rendered_input
    assert '"task_id": "task_running"' in rendered_input
    assert '"task_id": "task_blocked"' in rendered_input
    assert '"task_id": "task_done"' not in rendered_input
    assert '"task_id": "task_failed"' not in rendered_input
    assert '"goal": "Get weather in Shanghai"' in rendered_input
    assert '"goal": "Get weather in Beijing"' in rendered_input
    assert '"title": "Queued weather"' not in rendered_input
    assert '"status": "queued"' not in rendered_input


def test_build_response_instructions_emphasize_concise_spoken_replies():
    instructions = build_response_instructions()

    assert "spoken aloud" in instructions
    assert "one or two short sentences" in instructions
    assert "Summarize the full task result" in instructions


def test_build_interpreter_instructions_keep_core_routing_policy_compact():
    instructions = build_interpreter_instructions()

    assert "conversation_only is for social chat" in instructions
    assert "active_tasks" in instructions
    assert (
        "create_task and update_task, always provide a concrete non-empty goal"
        in instructions
    )
    assert "Prefer update_task or control_task over create_task" in instructions
    assert len(instructions) < 1400


def test_build_response_input_includes_message_history():
    action = ConversationAction(
        action_id="conv_1",
        action_type=ConversationActionType.CHAT_REPLY,
        metadata={
            "user_message": "what now?",
            "message_history": [
                {"role": "user", "text": "hello", "message_id": "m1"},
                {"role": "assistant", "text": "hi", "message_id": "m2"},
            ],
        },
    )

    rendered_input = build_response_input(action)

    assert '"message_history"' in rendered_input
    assert '"text": "hi"' in rendered_input


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
    assert request_payload["prompt_cache_key"] == INTERPRETER_PROMPT_CACHE_KEY
    assert provider._client.responses.last_parse_kwargs is not None
    assert provider._client.responses.last_parse_kwargs["prompt_cache_key"] == INTERPRETER_PROMPT_CACHE_KEY
    assert "parsed_output" in response_payload
    assert_duration_ms(response_payload)
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
    assert_duration_ms(response_payload)
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
    response_payload = snapshot.recent_traces[1].payload
    assert response_payload["output_text"] == "Hello world"
    assert response_payload["streamed"] is True
    assert_duration_ms(response_payload)
    assert "ttfb_ms" in response_payload
    assert isinstance(response_payload["ttfb_ms"], int | float)
    assert response_payload["ttfb_ms"] >= 0


def test_openai_provider_emits_interpreter_error_trace_payloads():
    settings = Settings(openai_api_key="test-key")
    trace_store = TraceStateStore()
    provider = OpenAIProvider(
        settings,
        client=FailingOpenAIClient(parse_error=RuntimeError("parse unavailable")),
    )

    with pytest.raises(LLMInvocationError, match="OpenAI structured call failed: parse unavailable"):
        asyncio.run(
            provider.parse_structured(
                instructions="interpret this",
                input_text='{"message_id":"message_1"}',
                schema=InterpretationEnvelope,
                trace_state_store=trace_store,
                session_id="session_test",
                span_id="span_4",
                related_message_id="message_1",
            )
        )

    snapshot = trace_store.snapshot("session_test")
    assert [event.event_type for event in snapshot.recent_traces] == [
        "llm_interpreter_request",
        "llm_interpreter_error",
    ]
    error_payload = snapshot.recent_traces[1].payload
    assert error_payload["error"] == "parse unavailable"
    assert_duration_ms(error_payload)


def test_openai_provider_emits_response_error_trace_payloads():
    settings = Settings(openai_api_key="test-key")
    trace_store = TraceStateStore()
    provider = OpenAIProvider(
        settings,
        client=FailingOpenAIClient(create_error=RuntimeError("generation unavailable")),
    )

    with pytest.raises(LLMInvocationError, match="OpenAI text generation failed: generation unavailable"):
        asyncio.run(
            provider.render_text(
                instructions="reply naturally",
                input_text='{"action_type":"acknowledge"}',
                trace_state_store=trace_store,
                session_id="session_test",
                span_id="span_5",
                related_message_id="message_1",
            )
        )

    snapshot = trace_store.snapshot("session_test")
    assert [event.event_type for event in snapshot.recent_traces] == [
        "llm_response_request",
        "llm_response_error",
    ]
    error_payload = snapshot.recent_traces[1].payload
    assert error_payload["error"] == "generation unavailable"
    assert_duration_ms(error_payload)


def test_openai_provider_stream_text_fallback_emits_duration_without_ttfb():
    settings = Settings(openai_api_key="test-key")
    trace_store = TraceStateStore()
    provider = OpenAIProvider(
        settings,
        client=FakeOpenAIClientWithoutStream(text="Fallback response"),
    )

    async def collect():
        chunks = []
        async for chunk in provider.stream_text(
            instructions="reply naturally",
            input_text='{"action_type":"chat_reply"}',
            trace_state_store=trace_store,
            session_id="session_test",
            span_id="span_6",
            related_message_id="message_1",
        ):
            chunks.append(chunk)
        return chunks

    output = asyncio.run(collect())

    snapshot = trace_store.snapshot("session_test")
    assert output == ["Fallback response"]
    assert [event.event_type for event in snapshot.recent_traces] == [
        "llm_response_stream_request",
        "llm_response_stream_response",
    ]
    response_payload = snapshot.recent_traces[1].payload
    assert response_payload["output_text"] == "Fallback response"
    assert response_payload["streamed"] is False
    assert "ttfb_ms" not in response_payload
    assert_duration_ms(response_payload)
