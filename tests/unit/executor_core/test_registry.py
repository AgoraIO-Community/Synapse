from synopse.executor_adapters.mock import MockExecutor
from synopse.executor_core import ExecutorRegistry


def test_registry_register_and_get():
    registry = ExecutorRegistry()
    executor = MockExecutor()
    registry.register(executor)

    assert registry.list_executor_types() == ["mock"]
    assert registry.get("mock") is executor
