from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from synapse.config_home import SYNAPSE_ENV_FILE, SYNAPSE_GATEWAY_CONFIG_FILE
from synapse.envfile import load_env_file
from synapse.yaml_support import YAMLParseError, load_yaml_file


class ExecutorHostConfigError(RuntimeError):
    pass


@dataclass(slots=True)
class ExecutorHostSettings:
    enabled: bool = False
    synapse_base_url: str = "http://127.0.0.1:8000"
    host_id: str = ""
    enabled_executors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LoadedExecutorHostConfig:
    host_settings: ExecutorHostSettings
    executors: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None


DEFAULT_ENV_FILE = SYNAPSE_ENV_FILE


def load_executor_host_config(
    *,
    env_file: Path | None = None,
    config_file: Path | None = None,
) -> LoadedExecutorHostConfig:
    env_path = env_file or DEFAULT_ENV_FILE
    load_env_file(env_path, override=False)
    config_path = config_file or env_path.with_name(SYNAPSE_GATEWAY_CONFIG_FILE.name)
    if not config_path.exists():
        return LoadedExecutorHostConfig(host_settings=ExecutorHostSettings(), executors={}, source_path=None)
    try:
        raw = load_yaml_file(config_path)
    except YAMLParseError as exc:
        raise ExecutorHostConfigError(f"Invalid executor host YAML at {config_path}: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ExecutorHostConfigError(f"Executor host config root must be a mapping: {config_path}")
    version = raw.get("version")
    if version not in (None, 1):
        raise ExecutorHostConfigError(f"Unsupported executor host config version at {config_path}: {version}")

    host = _parse_host_settings(_resolve_env_placeholders(raw.get("executor_host") or {}, config_path), config_path)
    if not host.enabled:
        return LoadedExecutorHostConfig(host_settings=host, executors={}, source_path=config_path)
    raw_executors = raw.get("executors") or {}
    if not isinstance(raw_executors, dict):
        raise ExecutorHostConfigError(f"'executors' must be a mapping in {config_path}")
    executors = {
        slug: _resolve_env_placeholders(raw_executors.get(slug), config_path)
        for slug in host.enabled_executors
        if slug in raw_executors
    }
    return LoadedExecutorHostConfig(
        host_settings=host,
        executors=executors,
        source_path=config_path,
    )


def load_executor_host_settings(*, env_file: Path | None = None) -> ExecutorHostSettings:
    return load_executor_host_config(env_file=env_file).host_settings


def generate_executor_host_id() -> str:
    return f"host-{uuid4().hex[:8]}"


def _resolve_env_placeholders(value: Any, config_path: Path) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(next_value, config_path) for key, next_value in value.items()}
    if isinstance(value, list):
        return [_resolve_env_placeholders(item, config_path) for item in value]
    if isinstance(value, str) and value.startswith("$") and value.count("$") == 1:
        env_name = value[1:]
        env_value = os.getenv(env_name)
        if env_value in (None, ""):
            raise ExecutorHostConfigError(
                f"Missing environment variable {env_name} referenced by {config_path}"
            )
        return env_value
    return value


def _parse_host_settings(raw_host: Any, config_path: Path) -> ExecutorHostSettings:
    if raw_host is None:
        raw_host = {}
    if not isinstance(raw_host, dict):
        raise ExecutorHostConfigError(f"'executor_host' must be a mapping in {config_path}")
    enabled_executors = _parse_string_list(
        raw_host.get("enabled_executors") or [],
        field_name="executor_host.enabled_executors",
        config_path=config_path,
    )
    settings = ExecutorHostSettings(
        enabled=_parse_bool_value(
            raw_host.get("enabled", bool(enabled_executors)),
            field_name="executor_host.enabled",
            config_path=config_path,
        ),
        synapse_base_url=str(raw_host.get("synapse_base_url", "http://127.0.0.1:8000")),
        host_id=str(raw_host.get("host_id", "")),
        enabled_executors=enabled_executors,
    )
    if settings.enabled and not settings.host_id.strip():
        raise ExecutorHostConfigError(f"'executor_host.host_id' must be set in {config_path}")
    return settings


def _parse_bool_value(value: Any, *, field_name: str, config_path: Path) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ExecutorHostConfigError(f"'{field_name}' must be a boolean in {config_path}")


def _parse_string_list(value: Any, *, field_name: str, config_path: Path) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ExecutorHostConfigError(f"'{field_name}' must be a list of strings in {config_path}")
    return [item.strip() for item in value]
