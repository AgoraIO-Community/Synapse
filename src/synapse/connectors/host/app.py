from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from synapse.api.paths import api_path

from .config import ConnectorHostSettings, load_connector_host_settings
from .registry import create_connector_module_registry

CONNECTOR_HOST_IMPLEMENTATION_VERSION = "headless-connector-host.v1"


def include_enabled_connector_routes(
    app: FastAPI,
    settings: ConnectorHostSettings,
) -> None:
    if not settings.enabled or not settings.enabled_connectors:
        return

    registry = create_connector_module_registry(settings.enabled_connectors)
    for slug in settings.enabled_connectors:
        module = registry.get(slug)
        if module is None:
            continue
        app.include_router(module.build_router())


def create_app(settings: ConnectorHostSettings | None = None) -> FastAPI:
    settings = settings or load_connector_host_settings()
    app = FastAPI(
        title="Synapse Connector Host",
        openapi_url=api_path("/openapi.json"),
        docs_url=api_path("/docs"),
        redoc_url=api_path("/redoc"),
    )
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get(api_path("/health"))
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "enabled": settings.enabled,
            "connectors": settings.enabled_connectors,
            "implementation_version": CONNECTOR_HOST_IMPLEMENTATION_VERSION,
            "synapse_base_url": settings.synapse_base_url,
            "upstream_transport_mode": "direct",
        }

    include_enabled_connector_routes(app, settings)
    return app


app = create_app()
