import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication.model import ToolCall
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.executor_core import ExecutorCapabilities, ExecutorEvent, ExecutorEventType, ExecutorSession
from synapse.protocol import Task, TaskStatus, TaskSummary
from synapse.runtime import Settings
from synapse.runtime.container import RuntimeContainer


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
    timeout: float = 6.0,
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


class CancelAwareExecutor:
    def __init__(self) -> None:
        self._release = asyncio.Event()
        self._capabilities = ExecutorCapabilities(executor_type="cancel-aware", supports_cancel=True)

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="cancel-aware-session", executor_type="cancel-aware")

    async def cancel_run(self, run_id: str) -> None:
        self._release.set()

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(self, run, task, session):
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.PROGRESS,
            message="working",
        )
        await self._release.wait()
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.COMPLETED,
            message="should not surface",
        )


class QuestionThenCompleteExecutor:
    def __init__(self) -> None:
        self._capabilities = ExecutorCapabilities(
            executor_type="question-once",
            supports_follow_up=True,
        )

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="question-once-session", executor_type="question-once")

    async def cancel_run(self, run_id: str) -> None:
        return None

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(self, run, task, session):
        if task.latest_instruction and "The user answered the pending question:" in task.latest_instruction:
            yield ExecutorEvent(
                run_id=run.run_id,
                session_id=session.session_id,
                event_type=ExecutorEventType.PROGRESS,
                message="continuing",
            )
            yield ExecutorEvent(
                run_id=run.run_id,
                session_id=session.session_id,
                event_type=ExecutorEventType.COMPLETED,
                message="Done after answer.",
            )
            return
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.BLOCKED,
            message="Which project name should I use?",
        )


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


@pytest.mark.anyio
async def test_interaction_request_resolution_requeues_blocked_task_and_completes_follow_up():
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(QuestionThenCompleteExecutor())
        await session.blackboard.put_task(
            Task(
                task_id="task-question",
                root_task_id="task-question",
                title="Question task",
                goal="Question task",
                status=TaskStatus.QUEUED,
                preferred_executor="question-once",
            )
        )
        session.schedule_execution()

        waiting_snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: (
                len(snap["interaction_requests"]) == 1
                and snap["interaction_requests"][0]["status"] == "pending"
                and snap["tasks"][0]["status"] == "waiting_user_input"
            ),
            timeout=2.0,
        )
        request_id = waiting_snapshot["interaction_requests"][0]["request_id"]

        response = await client.post(
            f"/sessions/{session_id}/interaction-requests/{request_id}/resolve",
            json={"action": "answer", "answer_text": "Use Synopse"},
        )
        assert response.status_code == 200

        completed_snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "completed",
            timeout=2.0,
        )

        assert completed_snapshot["interaction_requests"][0]["status"] == "answered"
        assert completed_snapshot["attention_items"][0]["status"] == "acted"
        assert completed_snapshot["tasks"][0]["latest_instruction"]
        assert "Use Synopse" in completed_snapshot["tasks"][0]["latest_instruction"]


@pytest.mark.anyio
async def test_cancelled_task_does_not_emit_stale_completion_notification():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "forget it": ScriptedPlan(
                    conversational_act="acknowledge_and_hold",
                    tool_calls=[
                        ToolCall(
                            name="control_task",
                            args={
                                "reference": "cancelable",
                                "command_type": "cancel_task",
                            },
                        )
                    ],
                    reply_override="Okay, I won't continue with that.",
                ),
                "__default__": ScriptedPlan(
                    conversational_act="model_reply",
                    reply_override="Noted.",
                ),
            }
        ),
        settings=Settings(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(CancelAwareExecutor())
        await session.blackboard.put_task(
            Task(
                task_id="task-cancelable",
                root_task_id="task-cancelable",
                title="Cancelable task",
                goal="Cancelable task",
                status=TaskStatus.QUEUED,
                preferred_executor="cancel-aware",
            )
        )
        session.schedule_execution()
        await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "running",
            timeout=1.0,
        )
        session.history.append_assistant(
            session_id,
            "I'm working on Cancelable task right now.",
            focused_task_id="task-cancelable",
            affected_task_ids=["task-cancelable"],
        )

        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "forget it"},
        )

        assert response.status_code == 200
        await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "cancelled",
            timeout=1.0,
        )
        await asyncio.sleep(0.2)

        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        conversation = (await client.get(f"/sessions/{session_id}/conversation")).json()

        assert snapshot["tasks"][0]["status"] == "cancelled"
        assert snapshot["execution_runs"][0]["status"] == "cancelled"
        assert snapshot["notification_candidates"] == []
        assert not any(
            entry["role"] == "assistant" and entry["text"] == "should not surface"
            for entry in conversation["conversation_history"]
        )
