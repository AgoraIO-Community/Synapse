from __future__ import annotations

API_PREFIX = "/api"

# Keep legacy API-like prefixes reserved in the combined service so the SPA
# never claims old API URLs after the hard cutover to /api.
LEGACY_API_ROUTE_PREFIXES = {
    "health",
    "sessions",
    "messages",
    "commands",
    "interaction-requests",
    "personas",
    "executors",
    "connectors",
    "openapi.json",
    "docs",
    "redoc",
}

SERVICE_RESERVED_ROUTE_PREFIXES = {"api", *LEGACY_API_ROUTE_PREFIXES}


def api_path(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{API_PREFIX}{normalized}"
