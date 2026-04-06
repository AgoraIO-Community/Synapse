import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synopse.api.app import create_app
from synopse.communication.models import ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.protocol import Task, TaskStatus, TaskSummary
from synopse.runtime import Settings
from synopse.runtime.container import RuntimeContainer


async def _wait_for_snapshot(client: AsyncClient, session_id: str, predicate, timeout: float = 4.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        if predicate(snapshot):
            return snapshot
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected snapshot state.")
        await asyncio.sleep(0.05)


async def _wait_for_conversation(
    client: AsyncClient,
    session_id: str,
    predicate,
    timeout: float = 4.0,
):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        snapshot = (await client.get(f"/sessions/{session_id}/conversation")).json()
        if predicate(snapshot):
            return snapshot
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected conversation state.")
        await asyncio.sleep(0.05)


def _build_app():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="model_reply",
                    reply_override="Noted.",
                )
            }
        ),
        settings=Settings(),
    )
    return app


@pytest.mark.anyio
async def test_completed_notification_is_emitted_into_conversation_history():
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-done",
                root_task_id="task-done",
                title="Done task",
                goal="Done task",
                status=TaskStatus.QUEUED,
                preferred_executor="mock",
                metadata={"mock_summary": "Done from notification flow."},
            )
        )
        session.schedule_execution()

        conversation = await _wait_for_conversation(
            client,
            session_id,
            lambda snap: any(
                entry["role"] == "assistant" and entry["text"] == "Done from notification flow."
                for entry in snap["conversation_history"]
            ),
        )
        snapshot = (await client.get(f"/sessions/{session_id}")).json()

        assert any(
            candidate["candidate_type"] == "completed"
            and candidate["delivery_status"] == "emitted"
            for candidate in snapshot["notification_candidates"]
        )
        assert conversation["conversation_history"][-1]["text"] == "Done from notification flow."


@pytest.mark.anyio
async def test_blocked_notification_is_emitted_immediately():
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-blocked",
                root_task_id="task-blocked",
                title="Blocked task",
                goal="Blocked task",
                status=TaskStatus.QUEUED,
                preferred_executor="mock",
                metadata={"mock_behavior": "blocked", "mock_block_reason": "Need confirmation."},
            )
        )
        session.schedule_execution()

        conversation = await _wait_for_conversation(
            client,
            session_id,
            lambda snap: any(
                entry["role"] == "assistant" and entry["text"] == "Need confirmation."
                for entry in snap["conversation_history"]
            ),
            timeout=2.0,
        )
        snapshot = (await client.get(f"/sessions/{session_id}")).json()

        assert any(
            candidate["candidate_type"] == "blocked"
            and candidate["delivery_status"] == "emitted"
            for candidate in snapshot["notification_candidates"]
        )
        assert conversation["conversation_history"][-1]["text"] == "Need confirmation."


@pytest.mark.anyio
async def test_needs_input_summary_notification_can_emit_without_run_event():
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        await session.blackboard.put_task(
            Task(
                task_id="task-input",
                root_task_id="task-input",
                title="Input task",
                goal="Input task",
            )
        )
        await session.blackboard.put_summary(
            TaskSummary(
                task_id="task-input",
                conversational_summary="I need one more detail from you.",
                latest_user_visible_status="waiting_user_input",
                needs_user_input=True,
            )
        )

        conversation = await _wait_for_conversation(
            client,
            session_id,
            lambda snap: any(
                entry["role"] == "assistant"
                and entry["text"] == "I need one more detail from you."
                for entry in snap["conversation_history"]
            ),
            timeout=2.0,
        )
        snapshot = (await client.get(f"/sessions/{session_id}")).json()

        assert any(
            candidate["candidate_type"] == "needs_input"
            and candidate["delivery_status"] == "emitted"
            for candidate in snapshot["notification_candidates"]
        )
        assert conversation["conversation_history"][-1]["text"] == "I need one more detail from you."
