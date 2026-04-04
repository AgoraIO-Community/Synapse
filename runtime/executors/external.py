from __future__ import annotations

import asyncio

from runtime.executors.base import ExecutionCallback
from runtime.executors.external_backend import (
    ExternalExecutionRequest,
    ExternalExecutionResult,
    ExternalExecutorBackend,
)
from runtime.infrastructure.ids import new_id
from runtime.protocols.execution import ExecutionEvent, ExecutionEventType, ExecutorCapability
from runtime.protocols.tasks import Artifact, Task, TaskStatus


class ExternalAsyncExecutor:
    def __init__(self, backend: ExternalExecutorBackend, executor_id: str) -> None:
        self._backend = backend
        self._executor_id = executor_id
        self._running: dict[str, asyncio.Task] = {}
        self._runs: dict[str, object] = {}

    def get_capabilities(self) -> ExecutorCapability:
        return self._backend.get_capabilities()

    async def start_task(
        self, task: Task, callback: ExecutionCallback, *, session_id: str
    ) -> None:
        await self.cancel_task(task.task_id)
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
        request = ExternalExecutionRequest(
            run_id=new_id("run"),
            task_id=task.task_id,
            session_id=session_id,
            executor_id=self._executor_id,
            title=task.title,
            goal=task.goal,
            latest_instruction=task.latest_instruction,
            input_context=dict(task.input_context),
        )
        try:
            run = await self._backend.start(request)
        except Exception as exc:
            await callback(
                ExecutionEvent(
                    event_id=new_id("exec"),
                    task_id=task.task_id,
                    executor_id=self._executor_id,
                    event_type=ExecutionEventType.FAILED,
                    status=TaskStatus.FAILED,
                    progress_message=f"Executor failed to start task: {exc}",
                )
            )
            return

        self._runs[task.task_id] = run
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
        self._running[task.task_id] = asyncio.create_task(
            self._watch(task, run, callback), name=f"external-executor:{task.task_id}"
        )

    async def update_task(self, task: Task, patch: dict) -> None:
        task.input_context.update(patch)

    async def cancel_task(self, task_id: str) -> None:
        run = self._runs.pop(task_id, None)
        watcher = self._running.pop(task_id, None)
        if watcher is not None:
            watcher.cancel()
        if run is not None:
            await run.cancel()

    async def pause_task(self, task_id: str) -> None:
        raise NotImplementedError("Pause is not supported by this executor.")

    async def resume_task(
        self, task: Task, callback: ExecutionCallback, *, session_id: str
    ) -> None:
        raise NotImplementedError("Resume is not supported by this executor.")

    async def _watch(self, task: Task, run, callback: ExecutionCallback) -> None:
        try:
            result = await run.wait()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await callback(
                ExecutionEvent(
                    event_id=new_id("exec"),
                    task_id=task.task_id,
                    executor_id=self._executor_id,
                    event_type=ExecutionEventType.FAILED,
                    status=TaskStatus.FAILED,
                    progress_message=f"Executor run failed: {exc}",
                )
            )
            return
        finally:
            self._runs.pop(task.task_id, None)
            self._running.pop(task.task_id, None)

        await callback(self._result_to_event(task, result))

    def _result_to_event(
        self, task: Task, result: ExternalExecutionResult
    ) -> ExecutionEvent:
        artifacts = [
            Artifact(
                artifact_id=new_id("artifact"),
                task_id=task.task_id,
                artifact_type=artifact.artifact_type,
                name=artifact.name,
                mime_type=artifact.mime_type,
                uri=artifact.uri,
                inline_value=artifact.inline_value,
                metadata=artifact.metadata,
            )
            for artifact in result.artifacts
        ]
        if result.failure_reason:
            return ExecutionEvent(
                event_id=new_id("exec"),
                task_id=task.task_id,
                executor_id=self._executor_id,
                event_type=ExecutionEventType.FAILED,
                status=TaskStatus.FAILED,
                progress_message=result.failure_reason,
                metadata=result.metadata,
            )
        return ExecutionEvent(
            event_id=new_id("exec"),
            task_id=task.task_id,
            executor_id=self._executor_id,
            event_type=ExecutionEventType.COMPLETED,
            status=TaskStatus.DONE,
            progress_message=result.summary or "Task completed successfully.",
            progress_percent=1.0,
            artifacts_delta=artifacts,
            metadata=result.metadata,
        )
