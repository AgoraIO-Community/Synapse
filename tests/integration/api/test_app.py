import pytest
from httpx import ASGITransport, AsyncClient

from synapse.api import app as api_app_module
from synapse.api.app import create_app
from synapse.runtime import Settings


@pytest.mark.anyio
async def test_app_adds_cors_headers_for_configured_origins():
    app = create_app(
        settings=Settings(
            cors_allowed_origins=("https://synapse-ui.vercel.app",),
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.options(
            "/sessions",
            headers={
                "Origin": "https://synapse-ui.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://synapse-ui.vercel.app"


@pytest.mark.anyio
async def test_app_serves_frontend_build_root_and_assets(monkeypatch, tmp_path):
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>Workbench</body></html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")
    monkeypatch.setattr(api_app_module, "frontend_dist_dir", lambda: dist_dir)
    monkeypatch.setattr(api_app_module, "frontend_dist_index", lambda: dist_dir / "index.html")

    app = create_app(settings=Settings())

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


@pytest.mark.anyio
async def test_app_proxies_gateway_requests_and_streams_response(monkeypatch):
    fake_client = _FakeProxyClient(
        _FakeProxyResponse(
            status_code=200,
            headers={
                "content-type": "text/event-stream",
                "cache-control": "no-cache",
            },
            chunks=[b"data: hello\n\n", b"data: [DONE]\n\n"],
        )
    )
    monkeypatch.setattr(api_app_module, "gateway_proxy_base_url", lambda: "http://127.0.0.1:8010")

    app = create_app(settings=Settings())
    app.state.gateway_proxy_client = fake_client

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/gateway/agora-convoai/chat/completions?binding_id=binding-1",
            headers={"x-binding-id": "binding-1", "content-type": "application/json"},
            content=b'{"stream":true}',
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == "data: hello\n\ndata: [DONE]\n\n"
    request, stream = fake_client.requests[0]
    assert stream is True
    assert str(request.url) == "http://127.0.0.1:8010/gateway/agora-convoai/chat/completions?binding_id=binding-1"
    assert request.headers["x-binding-id"] == "binding-1"
    assert request.content == b'{"stream":true}'


@pytest.mark.anyio
async def test_app_returns_503_for_gateway_proxy_when_gateway_disabled(monkeypatch):
    monkeypatch.setattr(api_app_module, "gateway_proxy_base_url", lambda: None)
    app = create_app(settings=Settings())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/gateway/agora-convoai/config")

    assert response.status_code == 503
    assert response.json()["detail"] == "Gateway host is not enabled."
