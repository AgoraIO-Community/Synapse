from __future__ import annotations

import importlib

from synapse.executor_host.config import ExecutorHostSettings, LoadedExecutorHostConfig

executor_host_main = importlib.import_module("synapse.executor_host.__main__")


def test_main_returns_130_on_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr(
        executor_host_main,
        "load_executor_host_config",
        lambda: LoadedExecutorHostConfig(
            host_settings=ExecutorHostSettings(
                enabled=True,
                synapse_base_url="http://127.0.0.1:8000",
                host_id="host-1",
                enabled_executors=["codex"],
            ),
            executors={},
        ),
    )

    class FakeService:
        def __init__(self, *, settings, executors_config):
            self.settings = settings
            self.executors_config = executors_config

        def run_forever(self):
            return object()

    monkeypatch.setattr(executor_host_main, "ExecutorHostService", FakeService)
    monkeypatch.setattr(
        executor_host_main.asyncio,
        "run",
        lambda _awaitable: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    assert executor_host_main.main() == 130
    assert "[stop] executor host interrupted" in capsys.readouterr().out
