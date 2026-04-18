from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from synapse.config_home import SYNAPSE_ENV_FILE, SYNAPSE_GATEWAY_CONFIG_FILE
from synapse.envfile import load_env_file
from synapse.yaml_support import YAMLParseError, load_yaml_file


class GatewayConfigError(RuntimeError):
    pass


@dataclass(slots=True)
class GatewayHostSettings:
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8010
    public_base_url: str = "http://127.0.0.1:8010"
    synapse_base_url: str = "http://127.0.0.1:8000"
    cors_allowed_origins: list[str] = field(default_factory=list)
    enabled_gateways: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LoadedGatewayConfig:
    host_settings: GatewayHostSettings
    gateways: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None


DEFAULT_ENV_FILE = SYNAPSE_ENV_FILE
def load_gateway_config(
    *,
    env_file: Path | None = None,
    config_file: Path | None = None,
) -> LoadedGatewayConfig:
    env_path = env_file or DEFAULT_ENV_FILE
    load_env_file(env_path, override=False)

    config_path = config_file or env_path.with_name(SYNAPSE_GATEWAY_CONFIG_FILE.name)
    if not config_path.exists():
        return LoadedGatewayConfig(
            host_settings=GatewayHostSettings(),
            gateways={},
            source_path=None,
        )

    try:
        raw = load_yaml_file(config_path)
    except YAMLParseError as exc:
        raise GatewayConfigError(f"Invalid gateway YAML at {config_path}: {exc}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise GatewayConfigError(f"Gateway config root must be a mapping: {config_path}")

    version = raw.get("version")
    if version not in (None, 1):
        raise GatewayConfigError(f"Unsupported gateway config version at {config_path}: {version}")

    resolved_host = _resolve_env_placeholders(raw.get("host") or {}, config_path)
    host = _parse_host_settings(resolved_host, config_path)
    if not host.enabled:
        return LoadedGatewayConfig(
            host_settings=host,
            gateways={},
            source_path=config_path,
        )

    raw_gateways = raw.get("gateways") or {}
    if not isinstance(raw_gateways, dict):
        raise GatewayConfigError(f"'gateways' must be a mapping in {config_path}")

    gateways = {
        slug: _resolve_env_placeholders(raw_gateways.get(slug), config_path)
        for slug in host.enabled_gateways
        if slug in raw_gateways
    }

    return LoadedGatewayConfig(
        host_settings=host,
        gateways=gateways,
        source_path=config_path,
    )


def load_gateway_host_settings(*, env_file: Path | None = None) -> GatewayHostSettings:
    return load_gateway_config(env_file=env_file).host_settings


def _resolve_env_placeholders(value: Any, config_path: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: _resolve_env_placeholders(next_value, config_path)
            for key, next_value in value.items()
        }
    if isinstance(value, list):
        return [_resolve_env_placeholders(item, config_path) for item in value]
    if isinstance(value, str) and value.startswith("$") and value.count("$") == 1:
        env_name = value[1:]
        env_value = os.getenv(env_name)
        if env_value in (None, ""):
            raise GatewayConfigError(
                f"Missing environment variable {env_name} referenced by {config_path}"
            )
        return env_value
    return value


def _parse_host_settings(raw_host: Any, config_path: Path) -> GatewayHostSettings:
    if raw_host is None:
        raw_host = {}
    if not isinstance(raw_host, dict):
        raise GatewayConfigError(f"'host' must be a mapping in {config_path}")

    enabled_gateways = _parse_string_list(
        raw_host.get("enabled_gateways") or [],
        field_name="host.enabled_gateways",
        config_path=config_path,
    )
    cors_allowed_origins = _parse_string_list(
        raw_host.get("cors_allowed_origins") or [],
        field_name="host.cors_allowed_origins",
        config_path=config_path,
    )

    return GatewayHostSettings(
        enabled=_parse_bool_value(
            raw_host.get("enabled", bool(enabled_gateways)),
            field_name="host.enabled",
            config_path=config_path,
        ),
        host=str(raw_host.get("host", "0.0.0.0")),
        port=int(raw_host.get("port", 8010)),
        public_base_url=str(raw_host.get("public_base_url", "http://127.0.0.1:8010")),
        synapse_base_url=str(raw_host.get("synapse_base_url", "http://127.0.0.1:8000")),
        cors_allowed_origins=cors_allowed_origins,
        enabled_gateways=enabled_gateways,
    )


def _parse_bool_value(value: Any, *, field_name: str, config_path: Path) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise GatewayConfigError(f"'{field_name}' must be a boolean in {config_path}")


def _parse_string_list(value: Any, *, field_name: str, config_path: Path) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise GatewayConfigError(f"'{field_name}' must be a list of strings in {config_path}")
    return [item.strip() for item in value]
