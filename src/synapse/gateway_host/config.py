from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from synapse.envfile import load_env_file


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class GatewayHostSettings:
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8010
    public_base_url: str = "http://127.0.0.1:8010"
    synapse_base_url: str = "http://127.0.0.1:8000"
    enabled_modules: list[str] = field(default_factory=list)


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env.local"


def load_gateway_host_settings(*, env_file: Path | None = None) -> GatewayHostSettings:
    load_env_file(env_file or DEFAULT_ENV_FILE, override=False)
    raw_modules = os.getenv("SYNAPSE_GATEWAY_MODULES", "")
    modules = [item.strip() for item in raw_modules.split(",") if item.strip()]
    return GatewayHostSettings(
        enabled=_get_bool("SYNAPSE_GATEWAY_ENABLED", bool(modules)),
        host=os.getenv("SYNAPSE_GATEWAY_HOST", "0.0.0.0"),
        port=int(os.getenv("SYNAPSE_GATEWAY_PORT", "8010")),
        public_base_url=os.getenv("SYNAPSE_GATEWAY_PUBLIC_BASE_URL", "http://127.0.0.1:8010"),
        synapse_base_url=os.getenv("SYNAPSE_GATEWAY_SYNAPSE_BASE_URL", "http://127.0.0.1:8000"),
        enabled_modules=modules,
    )
