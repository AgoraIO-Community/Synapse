from __future__ import annotations

from runtime.executors.external import ExternalAsyncExecutor
from runtime.executors.codex.backend import CodexCliBackend
from runtime.infrastructure.config import Settings


class CodexExecutor(ExternalAsyncExecutor):
    def __init__(self, settings: Settings, executor_id: str) -> None:
        super().__init__(CodexCliBackend(settings, executor_id=executor_id), executor_id)
