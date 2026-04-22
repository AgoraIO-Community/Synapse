import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from synapse.edge import app as edge_app_module
from synapse.edge.app import EdgeSettings, create_app
from tests.helpers.asgi_websocket import ASGIWebSocketSession


class _FakeProxyResponse:
    def __init__(self, *, status_code: int, headers: dict[str, str], chunks: list[bytes]) -> None:
        self.status_code = status_code
        self.headers = headers
        self._chunks = chunks

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        return None


class _FakeProxyClient:
    def __init__(self, response: _FakeProxyResponse) -> None:
        self.response = response
        self.requests = []

    def build_request(self, method: str, url: str, *, headers: dict[str, str], content: bytes):
        from httpx import Request

        return Request(method, url, headers=headers, content=content)

    async def send(self, request, *, stream: bool):
        self.requests.append((request, stream))
        return self.response

    async def aclose(self) -> None:
        return None


class _FakeUpstreamWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages: asyncio.Queue[str | Exception] = asyncio.Queue()
        for message in messages:
            self._messages.put_nowait(message)
        self.sent: list[str | bytes] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def recv(self):
        item = await self._messages.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def send(self, payload: str | bytes) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        await self._messages.put(RuntimeError("closed"))


@pytest.mark.anyio
async def test_edge_serves_frontend_build_root_assets_and_spa(tmp_path):
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>Workbench</body></html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    app = create_app(settings=EdgeSettings(frontend_dist=dist_dir))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        root_response = await client.get("/")
        asset_response = await client.get("/assets/app.js")
        spa_response = await client.get("/workbench/tasks")
        missing_asset_response = await client.get("/assets/missing.js")

    assert root_response.status_code == 200
    assert "Workbench" in root_response.text
    assert asset_response.status_code == 200
    assert "console.log('ok');" in asset_response.text
    assert spa_response.status_code == 200
    assert "Workbench" in spa_response.text
    assert missing_asset_response.status_code == 404


@pytest.mark.anyio
async def test_edge_proxies_backend_http_requests(monkeypatch, tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    fake_client = _FakeProxyClient(
        _FakeProxyResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            chunks=[b'{"status":"ok"}'],
        )
    )
    monkeypatch.setattr(edge_app_module, "create_proxy_client", lambda: fake_client)

    app = create_app(
        settings=EdgeSettings(
            backend_base_url="http://127.0.0.1:8001",
            frontend_dist=dist_dir,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    request, stream = fake_client.requests[0]
    assert stream is True
    assert str(request.url) == "http://127.0.0.1:8001/health"


@pytest.mark.anyio
async def test_edge_proxies_gateway_requests_and_returns_503_when_disabled(monkeypatch, tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    fake_client = _FakeProxyClient(
        _FakeProxyResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            chunks=[b'{"ready":true}'],
        )
    )
    monkeypatch.setattr(edge_app_module, "create_proxy_client", lambda: fake_client)

    enabled_app = create_app(
        settings=EdgeSettings(
            backend_base_url="http://127.0.0.1:8001",
            gateway_base_url="http://127.0.0.1:8010",
            frontend_dist=dist_dir,
        )
    )
    disabled_app = create_app(
        settings=EdgeSettings(
            backend_base_url="http://127.0.0.1:8001",
            frontend_dist=dist_dir,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=enabled_app),
        base_url="http://testserver",
    ) as client:
        enabled_response = await client.get("/gateway/agora-convoai/config")

    async with AsyncClient(
        transport=ASGITransport(app=disabled_app),
        base_url="http://testserver",
    ) as client:
        disabled_response = await client.get("/gateway/agora-convoai/config")

    assert enabled_response.status_code == 200
    assert enabled_response.json() == {"ready": True}
    request, stream = fake_client.requests[0]
    assert stream is True
    assert str(request.url) == "http://127.0.0.1:8010/gateway/agora-convoai/config"
    assert disabled_response.status_code == 503
    assert "Gateway host is not enabled." in disabled_response.text


@pytest.mark.anyio
async def test_edge_proxies_session_stream_websocket(monkeypatch, tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    fake_upstream = _FakeUpstreamWebSocket(
        [
            '{"type":"hello"}',
            '{"type":"assistant_response_completed","request_id":"req-1"}',
        ]
    )
    opened_urls: list[str] = []

    def fake_open_proxy_websocket(url: str):
        opened_urls.append(url)
        return fake_upstream

    monkeypatch.setattr(edge_app_module, "open_proxy_websocket", fake_open_proxy_websocket)

    app = create_app(
        settings=EdgeSettings(
            backend_base_url="http://127.0.0.1:8001",
            frontend_dist=dist_dir,
        )
    )

    async with ASGIWebSocketSession(app, "/sessions/session-1/stream") as websocket:
        assert (await websocket.receive_json()) == {"type": "hello"}
        await websocket.send_json(
            {
                "type": "send_message",
                "request_id": "req-1",
                "text": "ping",
            }
        )
        assert (await websocket.receive_json()) == {
            "type": "assistant_response_completed",
            "request_id": "req-1",
        }

    assert opened_urls == ["ws://127.0.0.1:8001/sessions/session-1/stream"]
    assert fake_upstream.sent == ['{"type": "send_message", "request_id": "req-1", "text": "ping"}']
