from __future__ import annotations

import asyncio

import pytest

from synapse.executors.adapters import HostedExecutor
from synapse.executors.node.registry import ExecutorNodeRegistry
from synapse.executors.core import ExecutorEventType, ExecutorSession
from synapse.protocol import ExecutionRun, ExecutorNodeExecutor, RegisterNodeMessage, Task
from synapse.runtime.executor_node_manager import ExecutorNodeManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent_payloads: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent_payloads.append(payload)


async def _collect_events(executor: HostedExecutor, run: ExecutionRun, task: Task, session: ExecutorSession):
    return [event async for event in executor.run_task(run, task, session)]


@pytest.mark.anyio
async def test_hosted_executor_finishes_waiting_on_disconnect_before_reconnect(tmp_path):
    manager = ExecutorNodeManager(
        detached_executor_types=("codex",),
        registry=ExecutorNodeRegistry(path=tmp_path / "executor_nodes.yaml"),
    )
    first_socket = FakeWebSocket()
    second_socket = FakeWebSocket()
    first_issue = await manager.create_node(
        name="Node One",
        enabled_executors=["codex"],
    )
    second_issue = await manager.create_node(
        name="Node Two",
        enabled_executors=["codex"],
    )
    executor = HostedExecutor(
        executor_type="codex",
        manager=manager,
        supports_resume=True,
        supports_follow_up=True,
        supports_pause=True,
    )
    session = ExecutorSession(session_id="codex-hosted-1", executor_type="codex")
    task = Task(
        task_id="task-1",
        root_task_id="task-1",
        title="Hosted task",
        goal="Hosted task",
        preferred_executor="codex",
        metadata={"executor_node_id": first_issue.node.node_id},
    )
    run = ExecutionRun(
        run_id="run-1",
        task_id="task-1",
        execution_session_id="exec-1",
        executor_type="codex",
    )

    await manager.register_connection(
        first_socket,
        RegisterNodeMessage(
            node_id=first_issue.node.node_id,
            token=first_issue.token,
            executors=[ExecutorNodeExecutor(executor_type="codex")],
        ),
    )

    collector = asyncio.create_task(_collect_events(executor, run, task, session))

    deadline = asyncio.get_running_loop().time() + 1.0
    while not first_socket.sent_payloads:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Timed out waiting for dispatch command.")
        await asyncio.sleep(0)

    await manager.disconnect(websocket=first_socket, reason="connection_closed")
    await manager.register_connection(
        second_socket,
        RegisterNodeMessage(
            node_id=second_issue.node.node_id,
            token=second_issue.token,
            executors=[ExecutorNodeExecutor(executor_type="codex")],
        ),
    )

    events = await asyncio.wait_for(collector, timeout=1.0)

    assert [event.event_type for event in events] == [ExecutorEventType.WAITING_EXECUTOR]
    assert events[0].message == f"Waiting for executor node '{first_issue.node.node_id}' to reconnect."
    assert events[0].metadata == {
        "executor_node_id": first_issue.node.node_id,
        "availability_reason": "connection_closed",
    }
