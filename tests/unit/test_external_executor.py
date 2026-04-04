import asyncio

import pytest

from runtime.executors.external import ExternalAsyncExecutor
from runtime.executors.external_backend import (
    ExternalArtifact,
    ExternalExecutionRequest,
    ExternalExecutionResult,
)
from runtime.protocols.execution import ExecutorCapability
from runtime.protocols.tasks import Task


class FakeRun:
    def __init__(self, result: ExternalExecutionResult) -> None:
        self._result = result
        self.cancelled = False

    async def wait(self) -> ExternalExecutionResult:
        await asyncio.sleep(0)
        return self._result

    async def cancel(self) -> None:
        self.cancelled = True


class BlockingRun:
    def __init__(self) -> None:
        self.cancelled = False
        self._gate = asyncio.Event()

    async def wait(self) -> ExternalExecutionResult:
        await self._gate.wait()
        return ExternalExecutionResult(summary="done")

    async def cancel(self) -> None:
        self.cancelled = True
        self._gate.set()


class FakeBackend:
    def __init__(
        self,
        result: ExternalExecutionResult | None = None,
        *,
        error: Exception | None = None,
        run=None,
    ) -> None:
        self._result = result or ExternalExecutionResult(summary="done")
        self._error = error
        self._run = run
        self.requests: list[ExternalExecutionRequest] = []

    def get_capabilities(self) -> ExecutorCapability:
        return ExecutorCapability(
            executor_id="external_executor",
            label="External Executor",
            supports_cancel=True,
            supports_streaming=False,
        )

    async def start(self, request: ExternalExecutionRequest):
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._run or FakeRun(self._result)


def make_task() -> Task:
    return Task(
        task_id="task_123",
        root_task_id="task_123",
        title="Implement change",
        goal="Implement change",
    )


@pytest.mark.anyio
async def test_external_executor_emits_completed_event_with_artifacts():
    backend = FakeBackend(
        ExternalExecutionResult(
            summary="Completed externally.",
            artifacts=[
                ExternalArtifact(
                    artifact_type="text",
                    name="summary",
                    inline_value="Completed externally.",
                )
            ],
        )
    )
    executor = ExternalAsyncExecutor(backend, "external_executor")
    task = make_task()
    events = []

    async def callback(event):
        events.append(event)

    await executor.start_task(task, callback, session_id="session_1")
    for _ in range(10):
        if len(events) == 3:
            break
        await asyncio.sleep(0)

    assert [event.event_type.value for event in events] == [
        "accepted",
        "started",
        "completed",
    ]
    assert events[-1].artifacts_delta[0].inline_value == "Completed externally."
    assert backend.requests[0].session_id == "session_1"


@pytest.mark.anyio
async def test_external_executor_emits_failed_event_when_backend_cannot_start():
    executor = ExternalAsyncExecutor(
        FakeBackend(error=RuntimeError("backend unavailable")),
        "external_executor",
    )
    task = make_task()
    events = []

    async def callback(event):
        events.append(event)

    await executor.start_task(task, callback, session_id="session_1")

    assert [event.event_type.value for event in events] == ["accepted", "failed"]
    assert "backend unavailable" in (events[-1].progress_message or "")


@pytest.mark.anyio
async def test_external_executor_cancel_stops_active_run():
    run = BlockingRun()
    executor = ExternalAsyncExecutor(
        FakeBackend(run=run),
        "external_executor",
    )
    task = make_task()

    async def callback(_event):
        return None

    await executor.start_task(task, callback, session_id="session_1")
    await executor.cancel_task(task.task_id)

    assert run.cancelled is True
