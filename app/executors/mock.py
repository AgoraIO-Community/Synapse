from __future__ import annotations

import asyncio

from app.executors.base import ExecutionCallback
from app.infrastructure.config import Settings
from app.infrastructure.ids import new_id
from app.protocols.execution import ExecutionEvent, ExecutionEventType, ExecutorCapability
from app.protocols.tasks import Artifact, Task, TaskStatus


class MockExecutor:
    def __init__(self, settings: Settings, executor_id: str) -> None:
        self._settings = settings
        self._executor_id = executor_id
        self._running: dict[str, asyncio.Task] = {}
        self._paused: dict[str, asyncio.Event] = {}

    def get_capabilities(self) -> ExecutorCapability:
        return ExecutorCapability(
            executor_id=self._executor_id,
            label="Mock Executor",
            capability_tags=["generic", "streaming", "interruptible"],
            supports_cancel=True,
            supports_pause=True,
            supports_streaming=True,
        )

    async def start_task(
        self, task: Task, callback: ExecutionCallback, *, session_id: str
    ) -> None:
        await self.cancel_task(task.task_id)
        pause_gate = asyncio.Event()
        pause_gate.set()
        self._paused[task.task_id] = pause_gate
        self._running[task.task_id] = asyncio.create_task(
            self._run(task, callback, paused_gate=pause_gate)
        )

    async def update_task(self, task: Task, patch: dict) -> None:
        task.input_context.update(patch)

    async def cancel_task(self, task_id: str) -> None:
        running = self._running.pop(task_id, None)
        if running is not None:
            running.cancel()
        self._paused.pop(task_id, None)

    async def pause_task(self, task_id: str) -> None:
        gate = self._paused.get(task_id)
        if gate:
            gate.clear()

    async def resume_task(
        self, task: Task, callback: ExecutionCallback, *, session_id: str
    ) -> None:
        gate = self._paused.get(task.task_id)
        if gate:
            gate.set()
            await callback(
                ExecutionEvent(
                    event_id=new_id("exec"),
                    task_id=task.task_id,
                    executor_id=self._executor_id,
                    event_type=ExecutionEventType.RESUMED,
                    status=TaskStatus.RUNNING,
                    progress_message="Task resumed.",
                )
            )
            if task.task_id not in self._running:
                await self.start_task(task, callback, session_id=session_id)
        else:
            await self.start_task(task, callback, session_id=session_id)

    async def _run(
        self,
        task: Task,
        callback: ExecutionCallback,
        *,
        paused_gate: asyncio.Event,
    ) -> None:
        await callback(
            ExecutionEvent(
                event_id=new_id("exec"),
                task_id=task.task_id,
                executor_id=self._executor_id,
                event_type=ExecutionEventType.ACCEPTED,
                status=TaskStatus.QUEUED,
                progress_message="Task accepted by executor.",
            )
        )
        await asyncio.sleep(self._settings.mock_executor_tick_seconds)
        await callback(
            ExecutionEvent(
                event_id=new_id("exec"),
                task_id=task.task_id,
                executor_id=self._executor_id,
                event_type=ExecutionEventType.STARTED,
                status=TaskStatus.RUNNING,
                progress_message="Task started.",
            )
        )
        await asyncio.sleep(self._settings.mock_executor_tick_seconds)
        await paused_gate.wait()
        await callback(
            ExecutionEvent(
                event_id=new_id("exec"),
                task_id=task.task_id,
                executor_id=self._executor_id,
                event_type=ExecutionEventType.PROGRESS,
                status=TaskStatus.RUNNING,
                progress_message="Task is making progress.",
                progress_percent=0.5,
            )
        )
        await asyncio.sleep(self._settings.mock_executor_tick_seconds)
        await paused_gate.wait()

        if task.input_context.get("simulate_blocked") and not task.input_context.get(
            "clarification_received"
        ):
            self._running.pop(task.task_id, None)
            await callback(
                ExecutionEvent(
                    event_id=new_id("exec"),
                    task_id=task.task_id,
                    executor_id=self._executor_id,
                    event_type=ExecutionEventType.BLOCKED,
                    status=TaskStatus.BLOCKED,
                    progress_message="Task needs clarification before it can continue.",
                )
            )
            return

        artifact = Artifact(
            artifact_id=new_id("artifact"),
            task_id=task.task_id,
            artifact_type="text",
            name="summary",
            inline_value=f"Completed: {task.goal}",
        )
        self._running.pop(task.task_id, None)
        await callback(
            ExecutionEvent(
                event_id=new_id("exec"),
                task_id=task.task_id,
                executor_id=self._executor_id,
                event_type=ExecutionEventType.COMPLETED,
                status=TaskStatus.DONE,
                progress_message="Task completed successfully.",
                progress_percent=1.0,
                artifacts_delta=[artifact],
            )
        )
