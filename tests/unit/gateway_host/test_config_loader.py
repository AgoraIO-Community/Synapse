from __future__ import annotations

from pathlib import Path

from synapse.gateway_host.config import load_gateway_config


def test_load_gateway_config_skips_disabled_gateway_env_resolution(tmp_path: Path, monkeypatch):
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
                "host:",
                "  enabled: true",
                "  enabled_gateways:",
                "    - agora-convoai",
                "gateways:",
                "  agora-convoai:",
                "    app_id: $AGORA_APP_ID",
                "    app_certificate: $AGORA_APP_CERTIFICATE",
                "  future-gateway:",
                "    app_id: $MISSING_APP_ID",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MISSING_APP_ID", raising=False)

    loaded = load_gateway_config(env_file=env_file)

    assert loaded.host_settings.enabled_gateways == ["agora-convoai"]
    assert "agora-convoai" in loaded.gateways
    assert "future-gateway" not in loaded.gateways


def test_load_gateway_config_skips_all_gateway_resolution_when_host_disabled(
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
                "host:",
                "  enabled: false",
                "  enabled_gateways:",
                "    - agora-convoai",
                "gateways:",
                "  agora-convoai:",
                "    app_id: $MISSING_APP_ID",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MISSING_APP_ID", raising=False)

    loaded = load_gateway_config(env_file=env_file)

    assert loaded.host_settings.enabled is False
    assert loaded.gateways == {}
