from types import SimpleNamespace

import pytest

from runtime.executors import bootstrap as bootstrap_module
from runtime.executors.errors import UnsupportedExecutorCommandError
from runtime.infrastructure.config import Settings
from runtime.infrastructure.ids import new_id
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
from runtime.protocols.tasks import ControlCommand, ControlCommandType, Task, TaskReference, TaskReferenceType, TaskStatus


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
async def test_unsupported_pause_command_is_rejected_without_mutating_task(monkeypatch):
    monkeypatch.setenv("SYNOPSE_CODEX_EXECUTOR_ENABLED", "true")
    monkeypatch.setattr(bootstrap_module, "_codex_cli_available", lambda _: True)

    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    task = Task(
        task_id="task_codex",
        root_task_id="task_codex",
        title="Codex task",
        goal="Codex task",
        status=TaskStatus.RUNNING,
        assigned_executor="codex_executor",
        candidate_executors=["codex_executor"],
    )
    session.task_registry[task.task_id] = task

    command = ControlCommand(
        command_id=new_id("cmd"),
        target_task_ref=TaskReference(
            reference_type=TaskReferenceType.TASK_ID,
            value=task.task_id,
        ),
        target_task_id=task.task_id,
        command_type=ControlCommandType.PAUSE_TASK,
    )

    with pytest.raises(UnsupportedExecutorCommandError):
        await services.execution_orchestrator.apply_control_command(
            session.session_id, command
        )

    assert session.task_registry[task.task_id].status == TaskStatus.RUNNING


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


@pytest.mark.anyio
async def test_unsupported_resume_control_from_message_bundle_emits_reply_instead_of_raising(
    monkeypatch,
):
    monkeypatch.setenv("SYNOPSE_CODEX_EXECUTOR_ENABLED", "true")
    monkeypatch.setattr(bootstrap_module, "_codex_cli_available", lambda _: True)

    services = build_services(build_test_services())
    session = services.runtime_state_store.create_session()
    queue = services.runtime_state_store.subscribe(session.session_id)
    task = Task(
        task_id="task_codex",
        root_task_id="task_codex",
        title="Codex task",
        goal="Codex task",
        status=TaskStatus.RUNNING,
        assigned_executor="codex_executor",
        candidate_executors=["codex_executor"],
    )
    session.task_registry[task.task_id] = task

    bundle = ActionBundle(
        bundle_id="bundle_resume",
        message_id="message_resume",
        actions=[
            RuntimeAction(
                action_id="action_resume",
                action_type=RuntimeActionType.CONTROL_TASK,
                target_scope=TargetScope.EXISTING_TASK,
                target_task_ref=TaskReference(
                    reference_type=TaskReferenceType.TASK_ID,
                    value=task.task_id,
                ),
                payload={"command_type": "resume_task", "reason": "resume it"},
                execution_trigger=ExecutionTrigger.SOFT,
                scope_of_effect=ScopeOfEffect.TASK,
            )
        ],
    )

    await services.execution_orchestrator.process_bundle(session.session_id, bundle)

    event = await queue.get()

    assert event.event_type == "chat_reply"
    assert "does not support" in event.payload["action"]["render_text"].lower()
    assert session.task_registry[task.task_id].status == TaskStatus.RUNNING
