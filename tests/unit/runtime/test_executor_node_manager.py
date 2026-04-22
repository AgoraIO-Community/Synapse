from __future__ import annotations

import asyncio

import pytest

from synapse.protocol import ExecutorNodeExecutor, RegisterNodeMessage
from synapse.runtime.executor_node_manager import ExecutorNodeManager, RunDispatchState


@pytest.mark.anyio
async def test_disconnect_notifies_waiting_runs_and_clears_tracking():
    manager = ExecutorNodeManager(detached_executor_types=("codex",))
    first_socket = object()

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

    event = await stale_queue.get()
    assert event.event.event_type.value == "waiting_executor"
    assert event.event.message == "Waiting for executor node 'node-1' to reconnect."
    assert event.event.metadata == {
        "executor_node_id": "node-1",
        "availability_reason": "connection_closed",
    }
    assert manager._run_queues == {}
    assert manager._run_states == {}
