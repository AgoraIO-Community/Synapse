from __future__ import annotations

from pathlib import Path

import pytest

from synapse.executors.node.config import load_executor_node_config


def test_load_executor_node_config_reads_enabled_executors(tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "executor_node:",
                "  enabled: true",
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

    loaded = load_executor_node_config(env_file=env_file, config_file=config_file)

    assert loaded.node_settings.enabled_executors == ["codex"]
    assert loaded.executors["codex"]["command"] == "/opt/codex"


def test_load_executor_node_config_rejects_invalid_enabled_executors(tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "executor_node:",
                "  enabled: true",
                "  enabled_executors: codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="executor_node.enabled_executors"):
        load_executor_node_config(env_file=env_file, config_file=config_file)


def test_load_executor_node_config_allows_connection_values_to_be_missing(tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "executor_node:",
                "  enabled: true",
                "  enabled_executors:",
                "    - codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_executor_node_config(env_file=env_file, config_file=config_file)
    assert loaded.node_settings.node_id == ""
    assert loaded.node_settings.token == ""
