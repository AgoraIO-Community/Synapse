from runtime.executors import bootstrap as bootstrap_module
from runtime.executors.bootstrap import MOCK_EXECUTOR_ID, build_executor_runtime
from runtime.infrastructure.config import Settings


def test_build_executor_runtime_registers_mock_by_default():
    runtime = build_executor_runtime(Settings())

    assert runtime.default_executor_id == MOCK_EXECUTOR_ID
    assert runtime.registry.list_ids() == [MOCK_EXECUTOR_ID]


def test_build_executor_runtime_registers_codex_when_enabled(monkeypatch):
    monkeypatch.setattr(bootstrap_module, "_codex_cli_available", lambda _: True)

    runtime = build_executor_runtime(
        Settings(
            codex_executor_enabled=True,
        )
    )

    assert set(runtime.registry.list_ids()) == {"mock_executor", "codex_executor"}
    assert runtime.default_executor_id == "codex_executor"


def test_build_executor_runtime_falls_back_to_mock_when_configured_default_is_missing(
    monkeypatch,
):
    monkeypatch.setattr(bootstrap_module, "_codex_cli_available", lambda _: False)

    runtime = build_executor_runtime(
        Settings(
            codex_executor_enabled=True,
            default_executor_id="codex_executor",
        )
    )

    assert runtime.registry.list_ids() == [MOCK_EXECUTOR_ID]
    assert runtime.default_executor_id == MOCK_EXECUTOR_ID


def test_build_executor_runtime_honors_explicit_mock_default_when_codex_is_available(
    monkeypatch,
):
    monkeypatch.setattr(bootstrap_module, "_codex_cli_available", lambda _: True)

    runtime = build_executor_runtime(
        Settings(
            codex_executor_enabled=True,
            default_executor_id=MOCK_EXECUTOR_ID,
        )
    )

    assert set(runtime.registry.list_ids()) == {"mock_executor", "codex_executor"}
    assert runtime.default_executor_id == MOCK_EXECUTOR_ID
