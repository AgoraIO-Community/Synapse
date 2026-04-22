from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import GatewayHostSettings, load_gateway_host_settings
from .registry import create_gateway_module_registry

GATEWAY_HOST_IMPLEMENTATION_VERSION = "headless-gateway-host.v1"


def include_enabled_gateway_routes(
    app: FastAPI,
    settings: GatewayHostSettings,
) -> None:
    if not settings.enabled or not settings.enabled_gateways:
        return

    registry = create_gateway_module_registry(settings.enabled_gateways)
    for slug in settings.enabled_gateways:
        module = registry.get(slug)
        if module is None:
            continue
        app.include_router(module.build_router())


def create_app(settings: GatewayHostSettings | None = None) -> FastAPI:
    settings = settings or load_gateway_host_settings()
    app = FastAPI(title="Synapse Gateway Host")
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allowed_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "enabled": settings.enabled,
            "gateways": settings.enabled_gateways,
            "implementation_version": GATEWAY_HOST_IMPLEMENTATION_VERSION,
            "synapse_base_url": settings.synapse_base_url,
            "upstream_transport_mode": "direct",
        }

    include_enabled_gateway_routes(app, settings)
    return app


app = create_app()
