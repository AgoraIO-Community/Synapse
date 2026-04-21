from __future__ import annotations

from pathlib import Path

import pytest

from synapse.executor_host.config import load_executor_host_config


def test_load_executor_host_config_reads_enabled_executors(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "executor_host:",
                "  enabled: true",
                "  synapse_base_url: http://127.0.0.1:8000",
                "  host_id: host-1",
                "  host_token: $HOST_TOKEN",
                "  heartbeat_seconds: 9",
                "  enabled_executors:",
                "    - codex",
                "executors:",
                "  codex:",
                "    command: /opt/codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOST_TOKEN", "secret-token")
    loaded = load_executor_host_config(env_file=env_file, config_file=config_file)

    assert loaded.host_settings.enabled is True
    assert loaded.host_settings.host_id == "host-1"
    assert loaded.host_settings.host_token == "secret-token"
    assert loaded.host_settings.heartbeat_seconds == 9.0
    assert loaded.host_settings.enabled_executors == ["codex"]
    assert loaded.executors["codex"]["command"] == "/opt/codex"


def test_load_executor_host_config_rejects_invalid_enabled_executors(tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "executor_host:",
                "  enabled: true",
                "  enabled_executors: codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="executor_host.enabled_executors"):
        load_executor_host_config(env_file=env_file, config_file=config_file)
