import asyncio
import json
from types import SimpleNamespace

import pytest

from runtime.executors.base import transient_execution_update
from runtime.protocols.conversation import ConversationAction, ConversationActionType
from runtime.infrastructure.config import Settings
from runtime.llm.client import LLMServices
from runtime.llm.openai_client import OpenAIProvider
from runtime.main import build_services
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType
from runtime.protocols.tasks import Task, TaskStatus
from runtime.shared_blackboard.mutations import (
    append_message_history,
    associate_message_history_task,
    upsert_task,
)


class FakeResponses:
    def __init__(self) -> None:
        self.last_create_kwargs: dict | None = None

    def parse(self, **kwargs):
        return SimpleNamespace(output_parsed=None)

    def create(self, **kwargs):
        self.last_create_kwargs = kwargs
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


@pytest.mark.anyio
async def test_task_completion_response_uses_task_scoped_history_and_origin_message():
    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    session_state = services.runtime_state_store.get_session(session.session_id)

    task = Task(
        task_id="task_1",
        root_task_id="task_1",
        title="Check CPU",
        goal="Check CPU",
        created_from_message_id="message_origin",
    )
    upsert_task(session_state, task)

    append_message_history(
        session_state,
        role="user",
        text="what is my pc cpu usage",
        message_id="message_origin",
    )
    associate_message_history_task(
        session_state,
        message_id="message_origin",
        task_id=task.task_id,
    )
    append_message_history(
        session_state,
        role="assistant",
        text="I'll look into your PC's CPU usage now.",
        message_id="message_task_reply",
        task_id=task.task_id,
    )
    append_message_history(
        session_state,
        role="user",
        text="btw how are you doing?",
        message_id="message_other",
    )

    action = ConversationAction(
        action_id="conv_1",
        action_type=ConversationActionType.INFORM_DONE,
        target_task_id=task.task_id,
        reason="CPU usage is 1.48%.",
    )

    await services.execution_orchestrator.emit_conversation_action(
        session.session_id,
        action,
        related_task_id=task.task_id,
    )

    create_kwargs = services.llm_services.responder._provider._client.responses.last_create_kwargs
    assert create_kwargs is not None
    rendered_input = json.loads(create_kwargs["input"])

    assert rendered_input["user_message"] == "what is my pc cpu usage"
    assert [item["message_id"] for item in rendered_input["message_history"]] == [
        "message_origin",
        "message_task_reply",
    ]
