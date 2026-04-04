import asyncio
import json
from types import SimpleNamespace

import pytest

from runtime.infrastructure.ids import new_id
from runtime.infrastructure.config import Settings
from runtime.llm.client import LLMServices
from runtime.llm.interpreter_schema import (
    InterpreterAction,
    InterpretationEnvelope,
    InterpreterActionBundle,
    InterpreterRoutingDecision,
)
from runtime.llm.openai_client import OpenAIProvider
from runtime.main import build_services
from runtime.protocols.conversation import ConversationActionType, UserMessage
from runtime.protocols.runtime import (
    ActionBundle,
    ConversationMode,
    ExecutionTrigger,
    ResolverStrategy,
    RuntimeActionType,
    ScopeOfEffect,
    TargetScope,
)
from runtime.protocols.trace import TraceStage
from runtime.protocols.tasks import (
    ControlCommandType,
    Priority,
    TaskReference,
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


def make_interpretation(message_id: str, text: str) -> InterpretationEnvelope:
    lowered = text.lower()
    if (
        lowered in {"hi", "hello", "hey"}
        or "how are you" in lowered
        or "what does this system do" in lowered
    ):
        actions = [
            InterpreterAction(
                action_id="action_1",
                action_type=RuntimeActionType.APPLY_CONTEXT_PATCH,
                target_scope=TargetScope.SESSION,
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.NONE,
                scope_of_effect=ScopeOfEffect.SESSION,
                command_type=ControlCommandType.PAUSE_TASK,
                target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                target_task_reference_relation=TaskReferenceRelation.CURRENT,
                latest_user_goal=text,
            )
        ]
        conversation_mode = ConversationMode.CONVERSATION_ONLY
        priority = Priority.NORMAL
    elif "update" in lowered or "continue" in lowered:
        actions = [
            InterpreterAction(
                action_id="action_1",
                action_type=RuntimeActionType.UPDATE_TASK,
                target_scope=TargetScope.EXISTING_TASK,
                priority=Priority.HIGH,
                execution_trigger=ExecutionTrigger.SOFT,
                scope_of_effect=ScopeOfEffect.TASK,
                target_task_reference_type=TaskReferenceType.LATEST_ACTIVE,
                target_task_reference_relation=TaskReferenceRelation.CURRENT,
                latest_instruction=text,
            )
        ]
        actions.append(
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
                latest_user_goal=text,
            )
        )
        conversation_mode = ConversationMode.TASK
        priority = Priority.HIGH
    else:
        actions = [
            InterpreterAction(
                action_id="action_1",
                action_type=RuntimeActionType.CREATE_TASK,
                target_scope=TargetScope.NEW_TASK,
                priority=Priority.NORMAL,
                execution_trigger=ExecutionTrigger.HARD,
                scope_of_effect=ScopeOfEffect.TASK,
                title=text[:80],
                goal=text,
                simulate_blocked="need info" in lowered or "ask me" in lowered,
            )
        ]
        actions.append(
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
                latest_user_goal=text,
            )
        )
        conversation_mode = ConversationMode.TASK
        priority = Priority.NORMAL
    return InterpretationEnvelope(
        routing_decision=InterpreterRoutingDecision(
            decision_id="decision_1",
            message_id=message_id,
            conversation_mode=conversation_mode,
            task_action_enabled=conversation_mode == ConversationMode.TASK,
            priority_hint=priority,
            resolver_strategy=ResolverStrategy.IMPLICIT,
        ),
        action_bundle=InterpreterActionBundle(
            bundle_id="bundle_1",
            message_id=message_id,
            actions=actions,
        ),
    )


def build_test_services() -> LLMServices:
    settings = Settings(openai_api_key="test-key")

    class DynamicFakeOpenAIClient:
        def __init__(self):
            self.responses = self

        def parse(self, **kwargs):
            payload = json.loads(kwargs["input"])
            return SimpleNamespace(
                output_parsed=make_interpretation(
                    message_id=payload["message_id"],
                    text=payload["latest_user_message"],
                )
            )

        def create(self, **kwargs):
            payload = json.loads(kwargs["input"])
            action_type = payload["action_type"]
            if action_type == "chat_reply":
                return SimpleNamespace(output_text="Hey there.")
            if action_type == "inform_done":
                return SimpleNamespace(output_text="Here is the answer.")
            return SimpleNamespace(output_text="Understood. I am starting that now.")

    provider = OpenAIProvider(settings, client=DynamicFakeOpenAIClient())
    return LLMServices(settings, provider=provider)


@pytest.mark.anyio
async def test_runtime_message_pipeline_stream_events():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)

    message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="search flights to Tokyo tomorrow",
    )
    snapshot = services.runtime_state_store.snapshot(session.session_id)
    routing_decision, bundle = await services.action_router.route(message, snapshot)

    initial_action = services.interaction_policy.build_initial_action(
        routing_decision,
        bundle,
        user_message_text=message.text,
    )
    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        initial_action,
        related_message_id=message.message_id,
    )
    await services.execution_orchestrator.process_bundle(session.session_id, bundle)

    event_types: list[str] = []
    for _ in range(8):
        event = await asyncio.wait_for(queue.get(), timeout=1)
        event_types.append(event.event_type)
        if event.event_type == "completed":
            break

    assert "acknowledge" in event_types
    assert "task_created" in event_types
    assert "progress" in event_types
    assert "completed" in event_types


@pytest.mark.anyio
async def test_blocked_task_can_be_resumed_via_update_message():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)

    create_message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="draft an outreach email and ask me for details need info",
    )
    decision, bundle = await services.action_router.route(
        create_message, services.runtime_state_store.snapshot(session.session_id)
    )
    initial = services.interaction_policy.build_initial_action(
        decision,
        bundle,
        user_message_text=create_message.text,
    )
    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        initial,
        related_message_id=create_message.message_id,
    )
    await services.execution_orchestrator.process_bundle(session.session_id, bundle)

    blocked_seen = False
    for _ in range(8):
        event = await asyncio.wait_for(queue.get(), timeout=1)
        if event.event_type == "blocked":
            blocked_seen = True
            break
    assert blocked_seen is True

    update_message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="update that with the recipient and continue",
    )
    decision, bundle = await services.action_router.route(
        update_message, services.runtime_state_store.snapshot(session.session_id)
    )
    initial = services.interaction_policy.build_initial_action(
        decision,
        bundle,
        user_message_text=update_message.text,
    )
    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        initial,
        related_message_id=update_message.message_id,
    )
    if decision.needs_clarification:
        bundle = ActionBundle(
            bundle_id=bundle.bundle_id,
            message_id=bundle.message_id,
            actions=[
                action
                for action in bundle.actions
                if action.action_type == RuntimeActionType.APPLY_CONTEXT_PATCH
            ],
            relations=bundle.relations,
        )
    await services.execution_orchestrator.process_bundle(session.session_id, bundle)

    completed = False
    for _ in range(10):
        event = await asyncio.wait_for(queue.get(), timeout=1)
        if event.event_type == "completed":
            completed = True
            break
    assert completed is True


def test_publish_snapshot_emits_system_snapshot_event():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()

    event = asyncio.run(services.runtime_state_store.publish_snapshot(session.session_id))

    assert event.event_type == "session_snapshot"
    assert event.category == "system"
    assert event.session_id == session.session_id


@pytest.mark.anyio
async def test_regular_chat_emits_chat_reply_without_creating_task():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)

    message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="hi",
    )
    snapshot = services.runtime_state_store.snapshot(session.session_id)
    decision, bundle = await services.action_router.route(message, snapshot)

    assert decision.conversation_mode == ConversationMode.CONVERSATION_ONLY
    initial = services.interaction_policy.build_initial_action(
        decision,
        bundle,
        user_message_text=message.text,
    )
    assert initial.action_type == ConversationActionType.CHAT_REPLY

    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        initial,
        related_message_id=message.message_id,
    )
    if bundle.actions:
        await services.execution_orchestrator.process_bundle(session.session_id, bundle)

    received = []
    for _ in range(3):
        event = await asyncio.wait_for(queue.get(), timeout=1)
        received.append(event)
        if event.event_type == "context_patch_applied":
            break

    assert "task_created" not in [event.event_type for event in received]
    assert any(event.event_type == "chat_reply" for event in received)


@pytest.mark.anyio
async def test_capability_gated_question_creates_task_instead_of_chat_reply():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)

    message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="tell me what time is it",
    )
    snapshot = services.runtime_state_store.snapshot(session.session_id)
    decision, bundle = await services.action_router.route(message, snapshot)

    assert decision.conversation_mode == ConversationMode.TASK
    assert any(action.action_type == RuntimeActionType.CREATE_TASK for action in bundle.actions)

    initial = services.interaction_policy.build_initial_action(
        decision,
        bundle,
        user_message_text=message.text,
    )
    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        initial,
        related_message_id=message.message_id,
    )
    await services.execution_orchestrator.process_bundle(session.session_id, bundle)

    received_types = []
    for _ in range(8):
        event = await asyncio.wait_for(queue.get(), timeout=1)
        received_types.append(event.event_type)
        if event.event_type == "completed":
            break

    assert "chat_reply" not in received_types
    assert "acknowledge" in received_types
    assert "task_created" in received_types
    assert "completed" in received_types


@pytest.mark.anyio
async def test_trace_flow_emits_module_level_causality_events():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    trace_queue = services.trace_state_store.subscribe(session.session_id)

    message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="search flights to Tokyo tomorrow",
    )
    snapshot = services.runtime_state_store.snapshot(session.session_id)
    routing_decision, bundle = await services.action_router.route(
        message,
        snapshot,
        span_id="span_trace_1",
    )
    initial_action = services.interaction_policy.build_initial_action(
        routing_decision,
        bundle,
        user_message_text=message.text,
    )
    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        initial_action,
        related_message_id=message.message_id,
        span_id="span_trace_1",
    )
    await services.execution_orchestrator.process_bundle(
        session.session_id,
        bundle,
        span_id="span_trace_1",
    )
    await asyncio.sleep(0)

    stages: list[TraceStage] = []
    event_types: list[str] = []
    payloads_by_type: dict[str, dict] = {}
    for _ in range(20):
        try:
            trace = await asyncio.wait_for(trace_queue.get(), timeout=0.2)
        except TimeoutError:
            break
        stages.append(trace.stage)
        event_types.append(trace.event_type)
        payloads_by_type[trace.event_type] = trace.payload

    assert TraceStage.ACTION_ROUTER in stages
    assert TraceStage.MESSAGE_INTERPRETER in stages
    assert TraceStage.EXECUTION_ORCHESTRATOR in stages
    assert "routing_started" in event_types
    assert "interpreter_response_received" in event_types
    assert "bundle_processing_started" in event_types
    assert "llm_interpreter_request" in event_types
    assert "llm_interpreter_response" in event_types
    assert "llm_response_request" in event_types
    assert "llm_response_response" in event_types
    assert "instructions" in payloads_by_type["llm_interpreter_request"]
    assert "input" in payloads_by_type["llm_interpreter_request"]
    assert "parsed_output" in payloads_by_type["llm_interpreter_response"]
    assert "instructions" in payloads_by_type["llm_response_request"]
    assert "output_text" in payloads_by_type["llm_response_response"]
