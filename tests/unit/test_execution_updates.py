import asyncio
from types import SimpleNamespace

import pytest

from runtime.executors.base import transient_execution_update
from runtime.infrastructure.config import Settings
from runtime.llm.client import LLMServices
from runtime.llm.openai_client import OpenAIProvider
from runtime.main import build_services
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.tasks import Task, TaskStatus
from runtime.shared_blackboard.mutations import upsert_task


class FakeResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(output_parsed=None)

    def create(self, **kwargs):
        return SimpleNamespace(output_text="unused")


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()


def build_test_services() -> LLMServices:
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIProvider(settings, client=FakeOpenAIClient())
    return LLMServices(settings, provider=provider)


@pytest.mark.anyio
async def test_transient_execution_update_is_streamed_without_persisting_or_mutating_task():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)

    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Implement change",
        goal="Implement change",
    )
    upsert_task(services.runtime_state_store.get_session(session.session_id), task)

    await services.execution_orchestrator.handle_execution_update(
        session.session_id,
        transient_execution_update(
            ExecutionEvent(
                event_id="exec_1",
                task_id=task.task_id,
                executor_id="codex_executor",
                event_type=ExecutionEventType.PROGRESS,
                status=TaskStatus.RUNNING,
                progress_message="Running tests.",
            )
        ),
    )

    streamed = await asyncio.wait_for(queue.get(), timeout=1)
    stored_session = services.runtime_state_store.get_session(session.session_id)

    assert streamed.category.value == "execution"
    assert streamed.event_type == "progress"
    assert stored_session.event_log == []
    assert stored_session.task_registry[task.task_id].status == TaskStatus.QUEUED
    assert stored_session.conversation_state == {}
