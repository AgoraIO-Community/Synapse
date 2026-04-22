from __future__ import annotations

import importlib

from synapse.executors.node.config import ExecutorNodeSettings, LoadedExecutorNodeConfig

executor_node_main = importlib.import_module("synapse.executors.node.__main__")


def test_main_returns_130_on_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr(
        executor_node_main,
        "load_executor_node_config",
        lambda: LoadedExecutorNodeConfig(
            node_settings=ExecutorNodeSettings(
                enabled=True,
                synapse_base_url="http://127.0.0.1:8000",
                node_id="node-1",
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

    monkeypatch.setattr(executor_node_main, "ExecutorNodeService", FakeService)
    monkeypatch.setattr(
        executor_node_main.asyncio,
        "run",
        lambda _awaitable: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    assert executor_node_main.main() == 130
    assert "[stop] executor node interrupted" in capsys.readouterr().out
