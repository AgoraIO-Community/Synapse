import asyncio

import pytest

from runtime.infrastructure.ids import new_id
from runtime.main import build_services
from runtime.protocols.conversation import UserMessage
from runtime.protocols.runtime import ActionBundle, RuntimeActionType


@pytest.mark.anyio
async def test_runtime_message_pipeline_stream_events():
    services = build_services()
    session = services.store.create_session()
    queue = services.store.subscribe(session.session_id)

    message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="search flights to Tokyo tomorrow",
    )
    snapshot = services.store.snapshot(session.session_id)
    routing_decision, bundle = services.message_router.route(message, snapshot)

    initial_action = services.communication_interpreter.build_initial_action(
        routing_decision, bundle
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
    services = build_services()
    session = services.store.create_session()
    queue = services.store.subscribe(session.session_id)

    create_message = UserMessage(
        message_id=new_id("message"),
        session_id=session.session_id,
        text="draft an outreach email and ask me for details need info",
    )
    decision, bundle = services.message_router.route(
        create_message, services.store.snapshot(session.session_id)
    )
    initial = services.communication_interpreter.build_initial_action(decision, bundle)
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
    decision, bundle = services.message_router.route(
        update_message, services.store.snapshot(session.session_id)
    )
    initial = services.communication_interpreter.build_initial_action(decision, bundle)
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
