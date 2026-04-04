from __future__ import annotations

from dataclasses import dataclass
from shutil import which

from runtime.executors.codex.executor import CodexExecutor
from runtime.executors.mock.executor import MockExecutor
from runtime.executors.registry import ExecutorRegistry
from runtime.infrastructure.config import Settings


MOCK_EXECUTOR_ID = "mock_executor"


@dataclass(slots=True)
class ExecutorRuntime:
    registry: ExecutorRegistry
    default_executor_id: str


def _codex_cli_available(cli_path: str) -> bool:
    return which(cli_path) is not None


def build_executor_runtime(settings: Settings) -> ExecutorRuntime:
    registry = ExecutorRegistry()
    registry.register(MOCK_EXECUTOR_ID, MockExecutor(settings, executor_id=MOCK_EXECUTOR_ID))

    codex_available = (
        settings.codex_executor_enabled and _codex_cli_available(settings.codex_cli_path)
    )
    if codex_available:
        registry.register(
            settings.codex_executor_id,
            CodexExecutor(settings, executor_id=settings.codex_executor_id),
        )

    default_executor_id = settings.default_executor_id
    if default_executor_id is None:
        default_executor_id = (
            settings.codex_executor_id if codex_available else MOCK_EXECUTOR_ID
        )
    if default_executor_id not in registry.list_ids():
        default_executor_id = MOCK_EXECUTOR_ID

    return ExecutorRuntime(
        registry=registry,
        default_executor_id=default_executor_id,
    )
