import pytest

from newbro.executors.adapters.mock import MockExecutor
from newbro.executors.core import ExecutorRegistry, UnknownExecutorError


def test_registry_register_and_get():
    registry = ExecutorRegistry()
    executor = MockExecutor()
    registry.register(executor)

    assert registry.list_executor_types() == ["mock"]
    assert registry.get("mock") is executor


def test_registry_raises_unknown_executor_error_for_missing_executor():
    registry = ExecutorRegistry()

    with pytest.raises(UnknownExecutorError, match="Unknown executor: User"):
        registry.get("User")
