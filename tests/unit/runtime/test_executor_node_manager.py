from __future__ import annotations

import asyncio

import pytest

from synapse.protocol import ExecutorNodeExecutor, RegisterNodeMessage
from synapse.runtime.executor_node_manager import ExecutorNodeManager, RunDispatchState


@pytest.mark.anyio
async def test_register_connection_clears_stale_run_tracking_after_disconnect():
    manager = ExecutorNodeManager(detached_executor_types=("codex",))
    first_socket = object()
    second_socket = object()

    await manager.register_connection(
        first_socket,
        RegisterNodeMessage(
            node_id="node-1",
            executors=[ExecutorNodeExecutor(executor_type="codex")],
        ),
    )
    stale_queue: asyncio.Queue = asyncio.Queue()
    manager._run_queues["run-stale"] = stale_queue
    manager._run_states["run-stale"] = RunDispatchState(
        run_id="run-stale",
        execution_session_id="exec-stale",
        executor_type="codex",
    )

    await manager.disconnect(reason="connection_closed")
    assert "run-stale" in manager._run_queues
    assert "run-stale" in manager._run_states

    await manager.register_connection(
        second_socket,
        RegisterNodeMessage(
            node_id="node-2",
            executors=[ExecutorNodeExecutor(executor_type="codex")],
        ),
    )

    assert manager._run_queues == {}
    assert manager._run_states == {}

