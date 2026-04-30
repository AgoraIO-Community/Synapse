from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from newbro.connectors.host.config import load_connector_config


def force_yaml_fallback(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def test_load_connector_config_skips_disabled_connector_env_resolution(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text(
        "\n".join(
            [
                "AGORA_APP_ID=agora-app",
                "AGORA_APP_CERTIFICATE=agora-cert",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  codex_command: /opt/codex",
                "connector_host:",
                "  enabled: true",
                "  enabled_connectors:",
                "    - agora-convoai",
                "connectors:",
                "  agora-convoai:",
                "    app_id: $AGORA_APP_ID",
                "    app_certificate: $AGORA_APP_CERTIFICATE",
                "  future-connector:",
                "    app_id: $MISSING_APP_ID",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MISSING_APP_ID", raising=False)

    loaded = load_connector_config(env_file=env_file)

    assert loaded.host_settings.enabled_connectors == ["agora-convoai"]
    assert "agora-convoai" in loaded.connectors
    assert "future-connector" not in loaded.connectors


def test_load_connector_config_skips_all_connector_resolution_when_host_disabled(
    tmp_path: Path,
    monkeypatch,
):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "connector_host:",
                "  enabled: false",
                "  enabled_connectors:",
                "    - agora-convoai",
                "connectors:",
                "  agora-convoai:",
                "    app_id: $MISSING_APP_ID",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MISSING_APP_ID", raising=False)

    loaded = load_connector_config(env_file=env_file)

    assert loaded.host_settings.enabled is False
    assert loaded.connectors == {}


def test_load_connector_config_accepts_legacy_empty_connectors_shape_with_yaml_fallback(
    tmp_path: Path,
    monkeypatch,
):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "connector_host:",
                "  enabled: false",
                "  enabled_connectors:",
                "connectors:",
                "  {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    force_yaml_fallback(monkeypatch)

    loaded = load_connector_config(env_file=env_file)

    assert loaded.host_settings.enabled is False
    assert loaded.connectors == {}


def test_load_connector_config_reads_host_cors_allowed_origins(tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "connector_host:",
                "  enabled: true",
                "  cors_allowed_origins:",
                "    - https://app.example.com",
                "    - http://localhost:5173",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_connector_config(env_file=env_file)

    assert loaded.host_settings.cors_allowed_origins == [
        "https://app.example.com",
        "http://localhost:5173",
    ]


def test_load_connector_config_rejects_invalid_host_cors_allowed_origins(tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "connector_host:",
                "  enabled: true",
                "  cors_allowed_origins: https://app.example.com",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="connector_host.cors_allowed_origins"):
        load_connector_config(env_file=env_file)
