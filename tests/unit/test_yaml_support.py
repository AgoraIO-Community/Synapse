from __future__ import annotations

from pathlib import Path

from newbro.yaml_support import _load_simple_yaml


def test_simple_yaml_loader_accepts_inline_empty_flow_values(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "connector_host:",
                "  enabled_connectors: []",
                "connectors: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = _load_simple_yaml(config_file)

    assert loaded == {
        "version": 1,
        "connector_host": {"enabled_connectors": []},
        "connectors": {},
    }


def test_simple_yaml_loader_accepts_nested_empty_flow_mapping_block(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "connectors:",
                "  {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = _load_simple_yaml(config_file)

    assert loaded == {
        "version": 1,
        "connectors": {},
    }
