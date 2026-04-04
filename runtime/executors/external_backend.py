from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from runtime.executors.base import ExecutionCallback
from runtime.protocols.execution import ExecutorCapability


@dataclass(slots=True)
class ExternalArtifact:
    artifact_type: str
    name: str
    mime_type: str | None = None
    inline_value: str | dict[str, Any] | None = None
    uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExternalExecutionRequest:
    run_id: str
    task_id: str
    session_id: str
    executor_id: str
    title: str
    goal: str
    latest_instruction: str | None
    input_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExternalExecutionResult:
    summary: str | None = None
    blocked_reason: str | None = None
    failure_reason: str | None = None
    artifacts: list[ExternalArtifact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExternalExecutionRun(Protocol):
    async def wait(self) -> ExternalExecutionResult: ...

    async def cancel(self) -> None: ...


class ExternalExecutorBackend(Protocol):
    def get_capabilities(self) -> ExecutorCapability: ...

    async def start(
        self,
        request: ExternalExecutionRequest,
        update_callback: ExecutionCallback | None = None,
    ) -> ExternalExecutionRun: ...
