from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import mimetypes
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

import httpx
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
import websockets
from websockets.exceptions import ConnectionClosed


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FRONTEND_DIST_DIR = ROOT / "src" / "synapse" / "ui" / "dist"
BACKEND_ROUTE_PREFIXES = (
    "health",
    "sessions",
    "messages",
    "commands",
    "interaction-requests",
    "personas",
    "executors",
    "openapi.json",
    "docs",
    "redoc",
)
PROXY_REQUEST_EXCLUDED_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
PROXY_RESPONSE_EXCLUDED_HEADERS = {
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
WEBSOCKET_PROXY_TIMEOUT_SECONDS = 10.0


@dataclass(slots=True)
class EdgeSettings:
    backend_base_url: str = "http://127.0.0.1:8000"
    gateway_base_url: str | None = None
    frontend_dist: Path = DEFAULT_FRONTEND_DIST_DIR

    def __post_init__(self) -> None:
        self.backend_base_url = self.backend_base_url.rstrip("/")
        self.gateway_base_url = (
            self.gateway_base_url.rstrip("/") if self.gateway_base_url else None
        )
        self.frontend_dist = Path(self.frontend_dist)


def create_proxy_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(trust_env=False, timeout=None)


def _proxy_client(app: Starlette) -> httpx.AsyncClient:
    client = getattr(app.state, "proxy_client", None)
    if client is None:
        client = create_proxy_client()
        app.state.proxy_client = client
    return client


def open_proxy_websocket(url: str):
    return websockets.connect(
        url,
        proxy=None,
        open_timeout=WEBSOCKET_PROXY_TIMEOUT_SECONDS,
        close_timeout=WEBSOCKET_PROXY_TIMEOUT_SECONDS,
    )


def _filter_proxy_headers(headers, *, excluded: set[str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in excluded
    }


async def _stream_proxy_response(response: httpx.Response):
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await response.aclose()


def _frontend_file_response(path: Path) -> Response:
    media_type, _ = mimetypes.guess_type(path.name)
    if path.suffix == ".html":
        media_type = "text/html; charset=utf-8"
    return Response(
        content=path.read_bytes(),
        media_type=media_type or "application/octet-stream",
    )


def _resolve_frontend_asset(frontend_dist: Path, frontend_path: str) -> Path | None:
    dist_dir = frontend_dist.resolve()
    candidate = (dist_dir / frontend_path).resolve()
    try:
        candidate.relative_to(dist_dir)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def _is_backend_route(frontend_path: str) -> bool:
    if not frontend_path:
        return False
    return frontend_path.split("/", 1)[0] in BACKEND_ROUTE_PREFIXES


def _is_gateway_route(frontend_path: str) -> bool:
    return frontend_path == "gateway" or frontend_path.startswith("gateway/")


def _frontend_response(frontend_dist: Path, frontend_path: str) -> Response:
    index_path = frontend_dist / "index.html"
    if frontend_path:
        asset = _resolve_frontend_asset(frontend_dist, frontend_path)
        if asset is not None:
            return _frontend_file_response(asset)
        if "." in frontend_path.split("/")[-1]:
            raise HTTPException(status_code=404, detail="Not found.")

    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Frontend build is missing.")
    return _frontend_file_response(index_path)


def _upstream_url(base_url: str, path: str, query: str) -> str:
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/")
    encoded_path = quote(path, safe="/")
    request_path = f"{base_path}/{encoded_path}" if encoded_path else (base_path or "/")
    return urlunparse((parsed.scheme, parsed.netloc, request_path, "", query, ""))


def _upstream_websocket_url(base_url: str, path: str, query: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base_path = parsed.path.rstrip("/")
    encoded_path = quote(path, safe="/")
    request_path = f"{base_path}/{encoded_path}" if encoded_path else (base_path or "/")
    return urlunparse((scheme, parsed.netloc, request_path, "", query, ""))


async def _proxy_http_request(
    request: Request,
    *,
    client: httpx.AsyncClient,
    upstream_base_url: str,
    path: str,
) -> Response:
    upstream_url = _upstream_url(upstream_base_url, path, request.url.query)
    headers = _filter_proxy_headers(
        request.headers,
        excluded=PROXY_REQUEST_EXCLUDED_HEADERS,
    )
    body = await request.body()
    upstream_request = client.build_request(
        request.method,
        upstream_url,
        headers=headers,
        content=body,
    )
    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Proxy request failed: {exc}") from exc

    response_headers = _filter_proxy_headers(
        upstream_response.headers,
        excluded=PROXY_RESPONSE_EXCLUDED_HEADERS,
    )
    return StreamingResponse(
        _stream_proxy_response(upstream_response),
        status_code=upstream_response.status_code,
        headers=response_headers,
    )


async def _relay_client_to_upstream(client: WebSocket, upstream) -> None:
    try:
        while True:
            message = await client.receive()
            message_type = message["type"]
            if message_type == "websocket.disconnect":
                return
            if message_type != "websocket.receive":
                continue
            text = message.get("text")
            if isinstance(text, str):
                await upstream.send(text)
                continue
            payload = message.get("bytes")
            if payload is not None:
                await upstream.send(payload)
    except WebSocketDisconnect:
        return
    finally:
        await _close_upstream(upstream)


async def _relay_upstream_to_client(client: WebSocket, upstream) -> None:
    try:
        while True:
            payload = await upstream.recv()
            if isinstance(payload, bytes):
                await client.send_bytes(payload)
            else:
                await client.send_text(payload)
    except ConnectionClosed:
        return
    finally:
        await _close_client(client)


async def _close_upstream(upstream) -> None:
    try:
        await upstream.close()
    except Exception:
        return


async def _close_client(client: WebSocket, *, code: int = 1000) -> None:
    try:
        await client.close(code=code)
    except RuntimeError:
        return


async def _proxy_websocket(client: WebSocket, upstream_url: str) -> None:
    try:
        async with open_proxy_websocket(upstream_url) as upstream:
            await client.accept()
            client_to_upstream = asyncio.create_task(_relay_client_to_upstream(client, upstream))
            upstream_to_client = asyncio.create_task(_relay_upstream_to_client(client, upstream))
            done, pending = await asyncio.wait(
                {client_to_upstream, upstream_to_client},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise exc
    except Exception:
        await _close_client(client, code=1011)


def create_app(*, settings: EdgeSettings | None = None) -> Starlette:
    resolved_settings = settings or EdgeSettings()

    @asynccontextmanager
    async def lifespan(app: Starlette):
        app.state.proxy_client = create_proxy_client()
        try:
            yield
        finally:
            await app.state.proxy_client.aclose()

    async def http_entrypoint(request: Request) -> Response:
        path = request.path_params.get("path", "")
        if _is_gateway_route(path):
            gateway_base_url = resolved_settings.gateway_base_url
            if gateway_base_url is None:
                raise HTTPException(status_code=503, detail="Gateway host is not enabled.")
            return await _proxy_http_request(
                request,
                client=_proxy_client(request.app),
                upstream_base_url=gateway_base_url,
                path=path,
            )
        if request.method in {"GET", "HEAD"} and not _is_backend_route(path):
            return _frontend_response(resolved_settings.frontend_dist, path)
        return await _proxy_http_request(
            request,
            client=_proxy_client(request.app),
            upstream_base_url=resolved_settings.backend_base_url,
            path=path,
        )

    async def session_stream_proxy(websocket: WebSocket) -> None:
        path = websocket.url.path.lstrip("/")
        upstream_url = _upstream_websocket_url(
            resolved_settings.backend_base_url,
            path,
            websocket.url.query,
        )
        await _proxy_websocket(websocket, upstream_url)

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/", http_entrypoint, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
            Route(
                "/{path:path}",
                http_entrypoint,
                methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            ),
            WebSocketRoute("/sessions/{session_id}/stream", session_stream_proxy),
        ],
    )


app = create_app()
