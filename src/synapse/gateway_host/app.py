from __future__ import annotations

from fastapi import FastAPI

from .config import GatewayHostSettings, load_gateway_host_settings
from .registry import create_gateway_module_registry

GATEWAY_HOST_IMPLEMENTATION_VERSION = "headless-gateway-host.v1"


def create_app(settings: GatewayHostSettings | None = None) -> FastAPI:
    settings = settings or load_gateway_host_settings()
    app = FastAPI(title="Synapse Gateway Host")

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

    if not settings.enabled or not settings.enabled_gateways:
        return app

    registry = create_gateway_module_registry(settings.enabled_gateways)
    for slug in settings.enabled_gateways:
        module = registry.get(slug)
        if module is None:
            continue
        app.include_router(module.build_router())

    return app


app = create_app()
