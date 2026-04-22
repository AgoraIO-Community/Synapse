from __future__ import annotations

import asyncio
import io
import json

import pytest

from synapse.executors.core import ExecutorCapabilities
from synapse.executors.node.config import ExecutorNodeSettings
from synapse.executors.node.service import ExecutorNodeLifecycleReporter, ExecutorNodeService
import synapse.executors.node.service as service_module


class FakeExecutor:
    def get_capabilities(self) -> ExecutorCapabilities:
        return ExecutorCapabilities(
            executor_type="codex",
            supports_resume=True,
            supports_follow_up=True,
            supports_pause=True,
            supports_cancel=True,
        )


class FakeWebSocket:
    def __init__(self, incoming: list[object]):
        self._incoming = list(incoming)
        self.sent: list[dict[str, object]] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def recv(self) -> str:
        if not self._incoming:
            raise asyncio.CancelledError()
        next_item = self._incoming.pop(0)
        if isinstance(next_item, BaseException):
            raise next_item
        return json.dumps(next_item)


class FakeConnection:
    def __init__(self, websocket: FakeWebSocket):
        self._websocket = websocket

    async def __aenter__(self) -> FakeWebSocket:
        return self._websocket

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def build_service(monkeypatch: pytest.MonkeyPatch, *, reporter: ExecutorNodeLifecycleReporter) -> ExecutorNodeService:
    monkeypatch.setattr(
        ExecutorNodeService,
        "_build_executors",
        lambda self, _executors_config: {"codex": FakeExecutor()},
    )
    return ExecutorNodeService(
        settings=ExecutorNodeSettings(
            enabled=True,
            synapse_base_url="http://127.0.0.1:8000",
            node_id="node-1",
            enabled_executors=["codex"],
        ),
        executors_config={},
        reporter=reporter,
    )


@pytest.mark.anyio
async def test_run_forever_reports_retry_then_ready(monkeypatch: pytest.MonkeyPatch):
    stream = io.StringIO()
    reporter = ExecutorNodeLifecycleReporter(stream=stream)
    service = build_service(monkeypatch, reporter=reporter)
    websocket = FakeWebSocket(
        [
            {"type": "ack", "message_type": "register_node", "ok": True, "detail": "registered"},
            asyncio.CancelledError(),
        ]
    )
    attempts: list[object] = [
        OSError("connection refused"),
        FakeConnection(websocket),
    ]
    delays: list[float] = []

    def fake_connect(url: str, **kwargs) -> FakeConnection:
        assert url == "ws://127.0.0.1:8000/executors/control"
        assert kwargs["proxy"] is None
        attempt = attempts.pop(0)
        if isinstance(attempt, Exception):
            raise attempt
        return attempt

    async def fake_sleep(delay_seconds: float) -> None:
        delays.append(delay_seconds)

    monkeypatch.setattr(service_module.websockets, "connect", fake_connect)
    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await service.run_forever()

    output = stream.getvalue()
    assert "[start] executor node node_id=node-1 executors=codex synapse=http://127.0.0.1:8000" in output
    assert "[connect] executor node attempt=1 url=ws://127.0.0.1:8000/executors/control" in output
    assert (
        "[warn] executor node attempt=1 connect_failed=OSError: connection refused "
        "url=ws://127.0.0.1:8000/executors/control"
    ) in output
    assert "[retry] executor node retrying in 1.0s" in output
    assert "[connect] executor node attempt=2 url=ws://127.0.0.1:8000/executors/control" in output
    assert "[ready] executor node node_id=node-1 executors=codex synapse=http://127.0.0.1:8000" in output
    assert output.index("[connect] executor node attempt=2") < output.index("[ready] executor node")
    assert delays == [1.0]
    assert websocket.sent[0]["type"] == "register_node"


@pytest.mark.anyio
async def test_run_forever_reports_disconnect_after_ready(monkeypatch: pytest.MonkeyPatch):
    stream = io.StringIO()
    reporter = ExecutorNodeLifecycleReporter(stream=stream)
    service = build_service(monkeypatch, reporter=reporter)
    websocket = FakeWebSocket(
        [
            {"type": "ack", "message_type": "register_node", "ok": True, "detail": "registered"},
            RuntimeError("connection lost"),
        ]
    )
    delays: list[float] = []

    def fake_connect(url: str, **kwargs) -> FakeConnection:
        assert url == "ws://127.0.0.1:8000/executors/control"
        assert kwargs["proxy"] is None
        return FakeConnection(websocket)

    async def fake_sleep(delay_seconds: float) -> None:
        delays.append(delay_seconds)
        raise asyncio.CancelledError()

    monkeypatch.setattr(service_module.websockets, "connect", fake_connect)
    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await service.run_forever()

    output = stream.getvalue()
    assert "[ready] executor node node_id=node-1 executors=codex synapse=http://127.0.0.1:8000" in output
    assert (
        "[warn] executor node disconnected=RuntimeError: connection lost "
        "url=ws://127.0.0.1:8000/executors/control"
    ) in output
    assert "[retry] executor node retrying in 1.0s" in output
    assert delays == [1.0]
