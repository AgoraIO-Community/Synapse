from __future__ import annotations

import asyncio

import pytest

from newbro.executors.node.registry import ExecutorNodeRegistry
from newbro.protocol import ExecutorNodeExecutor, RegisterNodeMessage
from newbro.runtime.executor_node_manager import ExecutorNodeManager, RunDispatchState


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


@pytest.mark.anyio
async def test_sends_to_one_node_do_not_block_another(tmp_path):
    manager = ExecutorNodeManager(
        detached_executor_types=("codex",),
        registry=ExecutorNodeRegistry(path=tmp_path / "executor_nodes.yaml"),
    )
    first_issue = await manager.create_node(name="Node One", enabled_executors=["codex"])
    second_issue = await manager.create_node(name="Node Two", enabled_executors=["codex"])

    first_release = asyncio.Event()
    second_sent = asyncio.Event()

    class SlowSocket:
        def __init__(self, sent_event: asyncio.Event | None = None, release_event: asyncio.Event | None = None):
            self.sent_event = sent_event
            self.release_event = release_event

        async def send_json(self, payload: dict[str, object]) -> None:
            if self.sent_event is not None:
                self.sent_event.set()
            if self.release_event is not None:
                await self.release_event.wait()

    await manager.register_connection(
        SlowSocket(release_event=first_release),
        RegisterNodeMessage(
            node_id=first_issue.node.node_id,
            token=first_issue.token,
            executors=[ExecutorNodeExecutor(executor_type="codex")],
        ),
    )
    await manager.register_connection(
        SlowSocket(sent_event=second_sent),
        RegisterNodeMessage(
            node_id=second_issue.node.node_id,
            token=second_issue.token,
            executors=[ExecutorNodeExecutor(executor_type="codex")],
        ),
    )

    first_connection = manager._connections_by_node[first_issue.node.node_id]
    second_connection = manager._connections_by_node[second_issue.node.node_id]

    first_task = asyncio.create_task(manager._send_json(first_connection, {"type": "first"}))
    second_task = asyncio.create_task(manager._send_json(second_connection, {"type": "second"}))

    await asyncio.wait_for(second_sent.wait(), timeout=1.0)
    first_release.set()
    await asyncio.gather(first_task, second_task)
