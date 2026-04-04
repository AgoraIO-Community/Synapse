from types import SimpleNamespace

import pytest

from runtime.infrastructure.config import Settings
from runtime.llm.client import LLMServices
from runtime.protocols.runtime import (
    ActionBundle,
    ExecutionTrigger,
    RuntimeAction,
    RuntimeActionType,
    ScopeOfEffect,
    TargetScope,
)
from runtime.llm.openai_client import OpenAIProvider
from runtime.main import build_services
from runtime.protocols.tasks import Task


class FakeResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(output_parsed=None)

    def create(self, **kwargs):
        return SimpleNamespace(output_text="ok")


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()


def build_test_services() -> LLMServices:
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(settings, client=FakeOpenAIClient())
    return LLMServices(settings, provider=provider)


@pytest.mark.anyio
async def test_runtime_snapshot_exposes_executor_capabilities():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()

    snapshot = services.runtime_state_store.snapshot(session.session_id)

    assert {cap.executor_id for cap in snapshot.executor_capabilities} == {"mock_executor"}


@pytest.mark.anyio
async def test_capability_gated_task_is_blocked_when_only_mock_executor_is_available():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)
    bundle = ActionBundle(
        bundle_id="bundle_1",
        message_id="message_1",
        actions=[
            RuntimeAction(
                action_id="action_1",
                action_type=RuntimeActionType.CREATE_TASK,
                target_scope=TargetScope.NEW_TASK,
                payload={
                    "title": "Check CPU usage",
                    "goal": "Check CPU usage",
                    "input_context": {},
                },
                execution_trigger=ExecutionTrigger.HARD,
                scope_of_effect=ScopeOfEffect.TASK,
            )
        ],
    )

    await services.execution_orchestrator.process_bundle(session.session_id, bundle)

    event = await queue.get()
    snapshot = services.runtime_state_store.snapshot(session.session_id)

    assert snapshot.task_registry == []
    assert event.event_type == "chat_reply"
    assert "mock executor" in event.payload["action"]["render_text"].lower()
