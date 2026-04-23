from __future__ import annotations

import asyncio

import pytest

from synapse.executors.node.registry import ExecutorNodeRegistry
from synapse.protocol import ExecutorNodeExecutor, RegisterNodeMessage
from synapse.runtime.executor_node_manager import ExecutorNodeManager, RunDispatchState


@pytest.mark.anyio
async def test_disconnect_notifies_waiting_runs_and_clears_tracking(tmp_path):
    manager = ExecutorNodeManager(
        detached_executor_types=("codex",),
        registry=ExecutorNodeRegistry(path=tmp_path / "executor_nodes.yaml"),
    )
    first_socket = object()
    issue = await manager.create_node(
        name="Node One",
        enabled_executors=["codex"],
    )

    await manager.register_connection(
        first_socket,
        RegisterNodeMessage(
            node_id=issue.node.node_id,
            token=issue.token,
            executors=[ExecutorNodeExecutor(executor_type="codex")],
        ),
    )
    stale_queue: asyncio.Queue = asyncio.Queue()
    manager._run_queues["run-stale"] = stale_queue
    manager._run_states["run-stale"] = RunDispatchState(
        run_id="run-stale",
        execution_session_id="exec-stale",
        executor_type="codex",
        node_id=issue.node.node_id,
    )

    await manager.disconnect(websocket=first_socket, reason="connection_closed")

    event = await stale_queue.get()
    assert event.event.event_type.value == "waiting_executor"
    assert event.event.message == f"Waiting for executor node '{issue.node.node_id}' to reconnect."
    assert event.event.metadata == {
        "executor_node_id": issue.node.node_id,
        "availability_reason": "connection_closed",
    }
    assert manager._run_queues == {}
    assert manager._run_states == {}
