import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api.app import create_app
from synapse.communication.model import ToolCall
from synapse.communication.models import ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.executor_core import ExecutorCapabilities, ExecutorEvent, ExecutorEventType, ExecutorSession
from synapse.runtime.container import RuntimeContainer
from synapse.runtime import Settings
from synapse.protocol import Task, TaskStatus


class SlowExecutor:
    def __init__(self, delay_seconds: float = 0.2) -> None:
        self._delay_seconds = delay_seconds
        self._capabilities = ExecutorCapabilities(executor_type="slow")

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="slow-session", executor_type="slow")

    async def cancel_run(self, run_id: str) -> None:
        return None

    async def pause_run(self, run_id: str) -> None:
        return None

    async def run_task(self, run, task, session):
        await asyncio.sleep(self._delay_seconds)
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.COMPLETED,
            message="slow done",
        )


class CancelAwareExecutor:
    def __init__(self) -> None:
        self._release = asyncio.Event()
        self._capabilities = ExecutorCapabilities(executor_type="cancel-aware", supports_cancel=True)
        self.cancelled_runs: list[str] = []

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> ExecutorSession:
        return ExecutorSession(session_id="cancel-aware-session", executor_type="cancel-aware")

    async def cancel_run(self, run_id: str) -> None:
        self.cancelled_runs.append(run_id)
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
        # Simulate a stale terminal event after cancellation.
        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.COMPLETED,
            message="should not surface",
        )


async def _wait_for_snapshot(client: AsyncClient, session_id: str, predicate, timeout: float = 1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        if predicate(snapshot):
            return snapshot
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for expected snapshot state.")
        await asyncio.sleep(0.01)


@pytest.mark.anyio
async def test_messages_v2_create_task_and_run_tick():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "__default__": ScriptedPlan(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Check flights",
                                "goal": "Check flights",
                                "mock_safe": True,
                            },
                        )
                    ],
                )
            }
        ),
        settings=Settings(),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "Check flights"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["reply_text"]
        assert body["affected_task_ids"]

        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["execution_runs"]) == 1,
        )
        assert len(snapshot["tasks"]) == 1
        assert len(snapshot["execution_runs"]) == 1


@pytest.mark.anyio
async def test_messages_v2_returns_before_background_execution_finishes():
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(SlowExecutor())
        await session.blackboard.put_task(
            Task(
                task_id="task-slow",
                root_task_id="task-slow",
                title="Slow task",
                goal="Slow task",
                status=TaskStatus.QUEUED,
                preferred_executor="slow",
            )
        )

        started = asyncio.get_running_loop().time()
        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "hello"},
        )
        elapsed = asyncio.get_running_loop().time() - started

        assert response.status_code == 200
        assert elapsed < 0.15

        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "completed",
            timeout=1.0,
        )
        assert snapshot["execution_runs"][0]["status"] == "completed"


@pytest.mark.anyio
async def test_messages_v2_conversational_cancel_applies_runtime_command_and_stops_live_run():
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
    executor = CancelAwareExecutor()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_id = (await client.post("/sessions")).json()["session_id"]
        session = app.state.runtime_container.get_session(session_id)
        session.registry.register(executor)
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
        assert response.json()["reply_text"] == "Okay, I won't continue with that."

        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: snap["tasks"][0]["status"] == "cancelled",
            timeout=1.0,
        )

        assert executor.cancelled_runs == [snapshot["execution_runs"][0]["run_id"]]
        assert snapshot["execution_runs"][0]["status"] == "cancelled"
        assert snapshot["summaries"][0]["latest_user_visible_status"] == "cancelled"


@pytest.mark.anyio
async def test_messages_v2_current_work_reply_prefers_active_task_over_cancelled_history():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "what are you working with?": lambda context: ScriptedPlan(
                    conversational_act="inform_progress",
                    reply_override=(
                        f"I'm working on {context.active_tasks[0].title} right now."
                        if context.active_tasks
                        else "I'm not actively working on anything right now."
                    ),
                ),
                "__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")
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
        session.registry.register(SlowExecutor(delay_seconds=1.0))
        await session.blackboard.put_task(
            Task(
                task_id="task-cpu",
                root_task_id="task-cpu",
                title="Check PC CPU Usage",
                goal="Retrieve current CPU usage.",
                status=TaskStatus.CANCELLED,
                preferred_executor="mock",
            )
        )
        await session.blackboard.put_task(
            Task(
                task_id="task-weather",
                root_task_id="task-weather",
                title="Check Shanghai's Weather",
                goal="Retrieve today's weather for Shanghai.",
                status=TaskStatus.CREATED,
                preferred_executor="slow",
            )
        )

        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "what are you working with?"},
        )

        assert response.status_code == 200
        assert response.json()["reply_text"] == "I'm working on Check Shanghai's Weather right now."
        assert response.json()["affected_task_ids"] == []


@pytest.mark.anyio
async def test_messages_v2_short_stop_cancels_last_focused_task_not_unrelated_task():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "forget it": ScriptedPlan(
                    conversational_act="acknowledge_and_hold",
                    tool_calls=[
                        ToolCall(
                            name="control_task",
                            args={"task_id": "task-weather", "command_type": "cancel_task"},
                        )
                    ],
                    reply_override="Okay, I won't continue with Check Shanghai's Weather.",
                ),
                "__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")
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
        session.registry.register(SlowExecutor(delay_seconds=1.0))
        await session.blackboard.put_task(
            Task(
                task_id="task-cpu",
                root_task_id="task-cpu",
                title="Check PC CPU Usage",
                goal="Retrieve current CPU usage.",
                status=TaskStatus.CANCELLED,
                preferred_executor="mock",
            )
        )
        await session.blackboard.put_task(
            Task(
                task_id="task-weather",
                root_task_id="task-weather",
                title="Check Shanghai's Weather",
                goal="Retrieve today's weather for Shanghai.",
                status=TaskStatus.CREATED,
                preferred_executor="slow",
            )
        )

        session.history.append_assistant(
            session_id,
            "I'm working on Check Shanghai's Weather right now.",
            focused_task_id="task-weather",
            affected_task_ids=["task-weather"],
        )

        second = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "forget it"},
        )
        assert second.status_code == 200
        assert second.json()["reply_text"] == "Okay, I won't continue with Check Shanghai's Weather."

        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: any(task["task_id"] == "task-weather" and task["status"] == "cancelled" for task in snap["tasks"]),
            timeout=1.0,
        )
        task_status = {task["task_id"]: task["status"] for task in snapshot["tasks"]}
        assert task_status["task-weather"] == "cancelled"
        assert task_status["task-cpu"] == "cancelled"


@pytest.mark.anyio
async def test_messages_v2_continue_after_cancel_creates_new_task():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "i don't want to cancel it": ScriptedPlan(
                    conversational_act="acknowledge_and_start",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Check Shanghai's Weather",
                                "goal": "Retrieve today's weather for Shanghai.",
                                "preferred_executor": "mock",
                                "mock_safe": True,
                            },
                        ),
                        ToolCall(
                            name="update_task",
                            args={
                                "reference": "Check Shanghai's Weather",
                                "patch": {
                                    "priority": 8,
                                    "latest_instruction": "Use today's forecast.",
                                    "session_affinity": "workspace-1",
                                },
                            },
                        ),
                        ToolCall(
                            name="add_task_note",
                            args={"reference": "Check Shanghai's Weather", "note": "Use concise wording."},
                        ),
                        ToolCall(
                            name="add_constraint",
                            args={
                                "reference": "Check Shanghai's Weather",
                                "constraint": "Do not browse unrelated cities.",
                                "category": "scope",
                            },
                        ),
                    ],
                    reply_override="Okay, I'll start Check Shanghai's Weather again.",
                ),
                "__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")
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
        await session.blackboard.put_task(
            Task(
                task_id="task-weather-old",
                root_task_id="task-weather-old",
                title="Check Shanghai's Weather",
                goal="Retrieve today's weather for Shanghai.",
                status=TaskStatus.CANCELLED,
                priority=8,
                preferred_executor="mock",
                latest_instruction="Use today's forecast.",
                session_affinity="workspace-1",
                metadata={
                    "mock_safe": True,
                    "notes": ["Use concise wording."],
                    "constraints": [{"constraint": "Do not browse unrelated cities.", "category": "scope"}],
                },
            )
        )
        session.history.append_assistant(
            session_id,
            "Okay, I won't continue with Check Shanghai's Weather.",
            focused_task_id="task-weather-old",
            affected_task_ids=["task-weather-old"],
        )

        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "i don't want to cancel it"},
        )

        assert response.status_code == 200
        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["tasks"]) == 2,
            timeout=1.0,
        )
        recreated = [task for task in snapshot["tasks"] if task["task_id"] != "task-weather-old"]
        assert len(recreated) == 1
        assert recreated[0]["title"] == "Check Shanghai's Weather"
        assert {task["task_id"]: task["status"] for task in snapshot["tasks"]}["task-weather-old"] == "cancelled"


@pytest.mark.anyio
async def test_messages_v2_ambiguous_bundle_destination_correction_asks_clarification():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "oh it should be shanghai": ScriptedPlan(
                    conversational_act="request_clarification",
                    reply_override="Do you mean the destination should be Shanghai instead of Beijing?",
                ),
                "__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")
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
        await session.blackboard.put_task(
            Task(
                task_id="task-flight",
                root_task_id="task-flight",
                title="Find flights to Beijing",
                goal="Search and list available flights from Shanghai to Beijing for tomorrow.",
                status=TaskStatus.CREATED,
                preferred_executor="mock",
            )
        )
        await session.blackboard.put_task(
            Task(
                task_id="task-hotel",
                root_task_id="task-hotel",
                title="Book hotel in Beijing",
                goal="Find and book a hotel in Beijing for tomorrow.",
                status=TaskStatus.CREATED,
                preferred_executor="mock",
            )
        )
        session.history.append_assistant(
            session_id,
            "I've started finding flights to Beijing and booking a hotel there for tomorrow.",
            focused_task_id="task-flight",
            focused_task_ids=["task-flight", "task-hotel"],
            affected_task_ids=["task-flight", "task-hotel"],
        )

        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "oh it should be shanghai"},
        )

        assert response.status_code == 200
        assert response.json()["reply_text"] == "Do you mean the destination should be Shanghai instead of Beijing?"
        snapshot = (await client.get(f"/sessions/{session_id}")).json()
        assert len(snapshot["tasks"]) == 2
        assert {task["task_id"] for task in snapshot["tasks"]} == {"task-flight", "task-hotel"}


@pytest.mark.anyio
async def test_messages_v2_explicit_bundle_destination_correction_replaces_beijing_tasks():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "travel to Shanghai instead of Beijing": ScriptedPlan(
                    conversational_act="acknowledge_and_modify",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Find flights to Shanghai",
                                "goal": "Search and list available flights from Shanghai to Shanghai for tomorrow.",
                                "preferred_executor": "mock",
                                "mock_safe": True,
                            },
                        ),
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Book hotel in Shanghai",
                                "goal": "Find and book a hotel in Shanghai for tomorrow.",
                                "preferred_executor": "mock",
                                "mock_safe": True,
                            },
                        ),
                        ToolCall(
                            name="control_task",
                            args={"task_id": "task-flight", "command_type": "cancel_task"},
                        ),
                        ToolCall(
                            name="control_task",
                            args={"task_id": "task-hotel", "command_type": "cancel_task"},
                        ),
                    ],
                    reply_override="Okay, I replaced Beijing with Shanghai in those tasks.",
                ),
                "__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")
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
        await session.blackboard.put_task(
            Task(
                task_id="task-flight",
                root_task_id="task-flight",
                title="Find flights to Beijing",
                goal="Search and list available flights from Shanghai to Beijing for tomorrow.",
                status=TaskStatus.CREATED,
                preferred_executor="mock",
            )
        )
        await session.blackboard.put_task(
            Task(
                task_id="task-hotel",
                root_task_id="task-hotel",
                title="Book hotel in Beijing",
                goal="Find and book a hotel in Beijing for tomorrow.",
                status=TaskStatus.CREATED,
                preferred_executor="mock",
            )
        )
        session.history.append_assistant(
            session_id,
            "I've started finding flights to Beijing and booking a hotel there for tomorrow.",
            focused_task_id="task-flight",
            focused_task_ids=["task-flight", "task-hotel"],
            affected_task_ids=["task-flight", "task-hotel"],
        )

        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "travel to Shanghai instead of Beijing"},
        )

        assert response.status_code == 200
        assert response.json()["reply_text"] == "Okay, I replaced Beijing with Shanghai in those tasks."
        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["tasks"]) == 4
            and all(
                next(task for task in snap["tasks"] if task["task_id"] == task_id)["status"] == "cancelled"
                for task_id in ("task-flight", "task-hotel")
            ),
            timeout=1.0,
        )
        task_status = {task["task_id"]: task["status"] for task in snapshot["tasks"]}
        assert task_status["task-flight"] == "cancelled"
        assert task_status["task-hotel"] == "cancelled"
        replacement_tasks = [
            task for task in snapshot["tasks"] if task["task_id"] not in {"task-flight", "task-hotel"}
        ]
        assert len(replacement_tasks) == 2
        assert all("Shanghai" in task["title"] or "Shanghai" in task["goal"] for task in replacement_tasks)
        assert all("Beijing" not in task["title"] and "Beijing" not in task["goal"] for task in replacement_tasks)


@pytest.mark.anyio
async def test_messages_v2_explicit_to_correction_updates_destination_like_slots():
    app = create_app()
    app.state.runtime_container = RuntimeContainer(
        communication_model=ScriptedCommunicationModel(
            {
                "i mean to shanghai": ScriptedPlan(
                    conversational_act="acknowledge_and_modify",
                    tool_calls=[
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Book flight to Shanghai",
                                "goal": "Find and book a flight to Shanghai for tomorrow.",
                                "preferred_executor": "mock",
                                "mock_safe": True,
                            },
                        ),
                        ToolCall(
                            name="create_task",
                            args={
                                "title": "Book hotel in Shanghai",
                                "goal": "Find and book a hotel in Shanghai for tomorrow.",
                                "preferred_executor": "mock",
                                "mock_safe": True,
                            },
                        ),
                        ToolCall(
                            name="control_task",
                            args={"task_id": "task-flight", "command_type": "cancel_task"},
                        ),
                        ToolCall(
                            name="control_task",
                            args={"task_id": "task-hotel", "command_type": "cancel_task"},
                        ),
                    ],
                    reply_override="Okay, I updated the destination to Shanghai.",
                ),
                "__default__": ScriptedPlan(conversational_act="model_reply", reply_override="Noted.")
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
        await session.blackboard.put_task(
            Task(
                task_id="task-flight",
                root_task_id="task-flight",
                title="Book flight to Beijing",
                goal="Find and book a flight to Beijing for tomorrow.",
                status=TaskStatus.CREATED,
                preferred_executor="mock",
            )
        )
        await session.blackboard.put_task(
            Task(
                task_id="task-hotel",
                root_task_id="task-hotel",
                title="Book hotel in Beijing",
                goal="Find and book a hotel in Beijing for tomorrow.",
                status=TaskStatus.CREATED,
                preferred_executor="mock",
            )
        )
        session.history.append_assistant(
            session_id,
            "I've set up your flight and hotel tasks.",
            focused_task_id="task-flight",
            focused_task_ids=["task-flight", "task-hotel"],
            affected_task_ids=["task-flight", "task-hotel"],
        )

        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "i mean to shanghai"},
        )

        assert response.status_code == 200
        assert response.json()["reply_text"] == "Okay, I updated the destination to Shanghai."
        snapshot = await _wait_for_snapshot(
            client,
            session_id,
            lambda snap: len(snap["tasks"]) == 4,
            timeout=1.0,
        )
        replacement_tasks = [
            task for task in snapshot["tasks"] if task["task_id"] not in {"task-flight", "task-hotel"}
        ]
        assert any(task["title"] == "Book flight to Shanghai" for task in replacement_tasks)
        assert any(task["title"] == "Book hotel in Shanghai" for task in replacement_tasks)
