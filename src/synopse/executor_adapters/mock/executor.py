from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

from synopse.executor_core import (
    ExecutorCapabilities,
    ExecutorEvent,
    ExecutorEventType,
)
from synopse.protocol import ExecutionRun, Task

from .session import MockExecutorSession


class MockExecutor:
    def __init__(self) -> None:
        self._capabilities = ExecutorCapabilities(
            executor_type="mock",
            supports_resume=False,
            supports_follow_up=True,
            supports_pause=True,
            supports_cancel=True,
            supports_setup=False,
        )
        self.cancelled_runs: set[str] = set()
        self.paused_runs: set[str] = set()

    def get_capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    async def create_session(self, workspace_id: str | None = None) -> MockExecutorSession:
        return MockExecutorSession(
            session_id=f"mock-session-{uuid4().hex[:8]}",
            executor_type="mock",
            metadata={"workspace_id": workspace_id} if workspace_id else {},
        )

    async def cancel_run(self, run_id: str) -> None:
        self.cancelled_runs.add(run_id)

    async def pause_run(self, run_id: str) -> None:
        self.paused_runs.add(run_id)

    async def run_task(
        self,
        run: ExecutionRun,
        task: Task,
        session: MockExecutorSession,
    ) -> AsyncIterator[ExecutorEvent]:
        behavior = str(task.metadata.get("mock_behavior", "complete"))
        progress_messages = task.metadata.get("mock_progress_messages")
        if isinstance(progress_messages, list):
            for item in progress_messages:
                if isinstance(item, str) and item.strip():
                    yield ExecutorEvent(
                        run_id=run.run_id,
                        session_id=session.session_id,
                        event_type=ExecutorEventType.PROGRESS,
                        message=item.strip(),
                    )

        if behavior == "blocked":
            yield ExecutorEvent(
                run_id=run.run_id,
                session_id=session.session_id,
                event_type=ExecutorEventType.BLOCKED,
                message=str(
                    task.metadata.get(
                        "mock_block_reason",
                        "Waiting for additional user input.",
                    )
                ),
            )
            return

        if behavior == "failed":
            yield ExecutorEvent(
                run_id=run.run_id,
                session_id=session.session_id,
                event_type=ExecutorEventType.FAILED,
                message=str(task.metadata.get("mock_failure_reason", "Mock executor failed.")),
            )
            return

        yield ExecutorEvent(
            run_id=run.run_id,
            session_id=session.session_id,
            event_type=ExecutorEventType.COMPLETED,
            message=str(task.metadata.get("mock_summary", f"Completed: {task.title}")),
        )
