from __future__ import annotations

from contextlib import asynccontextmanager
import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
import httpx

from synapse.api.logging import install_access_log_filters
from synapse.api.routes.commands import router as commands_router
from synapse.api.routes.health import router as health_router
from synapse.api.routes.interaction_requests import router as interaction_requests_router
from synapse.api.routes.messages import router as messages_router
from synapse.api.routes.personas import router as personas_router
from synapse.api.routes.sessions import router as sessions_router
from synapse.api.ws.executors import router as executor_control_router
from synapse.api.ws.stream import router as stream_router
from synapse.gateway_host.config import GatewayConfigError, GatewayHostSettings, load_gateway_host_settings
from synapse.runtime.bootstrap import build_runtime_container
from synapse.runtime.config import Settings

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST_DIR = ROOT / "src" / "synapse" / "ui" / "dist"
FRONTEND_INDEX_FILE = "index.html"
RESERVED_FRONTEND_PREFIXES = (
    "health",
    "sessions",
    "gateway",
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


def frontend_dist_dir() -> Path:
    return FRONTEND_DIST_DIR


def frontend_dist_index() -> Path:
    return frontend_dist_dir() / FRONTEND_INDEX_FILE


def create_gateway_proxy_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(trust_env=False, timeout=None)


def gateway_proxy_base_url() -> str | None:
    try:
        settings = load_gateway_host_settings()
    except GatewayConfigError:
        return None
    if not settings.enabled or not settings.enabled_gateways:
        return None
    return f"http://{_gateway_proxy_host(settings)}:{settings.port}"


def _gateway_proxy_host(settings: GatewayHostSettings) -> str:
    if settings.host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return settings.host


def _request_gateway_url(base_url: str, gateway_path: str, query: str) -> str:
    encoded_path = quote(gateway_path, safe="/")
    path = f"{base_url}/gateway/{encoded_path}" if encoded_path else f"{base_url}/gateway"
    return f"{path}?{query}" if query else path


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


def _resolve_frontend_asset(frontend_path: str) -> Path | None:
    dist_dir = frontend_dist_dir().resolve()
    candidate = (dist_dir / frontend_path).resolve()
    try:
        candidate.relative_to(dist_dir)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def _is_reserved_frontend_path(frontend_path: str) -> bool:
    if not frontend_path:
        return False
    return frontend_path.split("/", 1)[0] in RESERVED_FRONTEND_PREFIXES


def create_app(*, settings: Settings | None = None) -> FastAPI:
    container = build_runtime_container(settings=settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await app.state.gateway_proxy_client.aclose()

    app = FastAPI(title="Synapse v2", lifespan=lifespan)
    app.state.runtime_container = container
    app.state.gateway_proxy_client = create_gateway_proxy_client()

    install_access_log_filters(container.settings)
    if container.settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(container.settings.cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(commands_router)
    app.include_router(interaction_requests_router)
    app.include_router(personas_router)
    app.include_router(stream_router)
    app.include_router(executor_control_router)

    @app.api_route(
        "/gateway/{gateway_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    async def proxy_gateway(request: Request, gateway_path: str):
        base_url = gateway_proxy_base_url()
        if base_url is None:
            raise HTTPException(status_code=503, detail="Gateway host is not enabled.")

        upstream_url = _request_gateway_url(base_url, gateway_path, request.url.query)
        headers = _filter_proxy_headers(
            request.headers,
            excluded=PROXY_REQUEST_EXCLUDED_HEADERS,
        )
        body = await request.body()
        upstream_request = app.state.gateway_proxy_client.build_request(
            request.method,
            upstream_url,
            headers=headers,
            content=body,
        )
        try:
            upstream_response = await app.state.gateway_proxy_client.send(
                upstream_request,
                stream=True,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"Gateway proxy request failed: {exc}") from exc

        response_headers = _filter_proxy_headers(
            upstream_response.headers,
            excluded=PROXY_RESPONSE_EXCLUDED_HEADERS,
        )
        return StreamingResponse(
            _stream_proxy_response(upstream_response),
            status_code=upstream_response.status_code,
            headers=response_headers,
        )

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def frontend_root():
        index_path = frontend_dist_index()
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail="Frontend build is missing.")
        return _frontend_file_response(index_path)

    @app.api_route("/{frontend_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def frontend_fallback(frontend_path: str):
        if _is_reserved_frontend_path(frontend_path):
            raise HTTPException(status_code=404, detail="Not found.")

        if frontend_path:
            asset = _resolve_frontend_asset(frontend_path)
            if asset is not None:
                return _frontend_file_response(asset)
            if "." in frontend_path.split("/")[-1]:
                raise HTTPException(status_code=404, detail="Not found.")

        index_path = frontend_dist_index()
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail="Frontend build is missing.")
        return _frontend_file_response(index_path)

    return app


app = create_app()
