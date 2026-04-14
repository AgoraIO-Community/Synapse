from __future__ import annotations

from pathlib import Path

from synapse.runtime import config as config_module


def configure_runtime_paths(monkeypatch, *, env_file: Path, config_file: Path) -> None:
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_FILE", config_file)


def clear_runtime_env(monkeypatch) -> None:
    for name in [
        "OPENAI_API_KEY",
        "SYNAPSE_OPENAI_MODEL",
        "SYNAPSE_OPENAI_TIMEOUT_SECONDS",
        "SYNAPSE_OPENAI_BASE_URL",
        "OPENAI_BASE_URL",
        "SYNAPSE_CODEX_EXECUTOR_ENABLED",
        "SYNAPSE_CODEX_COMMAND",
        "SYNAPSE_LOG_FORMAT",
        "SYNAPSE_LOG_COLOR",
        "SYNAPSE_QUIET_DIAGNOSTICS_ACCESS_LOGS",
        "SYNAPSE_LOG_LLM_DETAILS",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_load_settings_reads_openai_config(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "SYNAPSE_OPENAI_MODEL=gpt-4.1-mini",
                "SYNAPSE_OPENAI_TIMEOUT_SECONDS=45",
            ]
        )
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_timeout_seconds == 45.0


def test_load_settings_reads_log_output_config(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text(
        "\n".join(
            [
                "SYNAPSE_LOG_FORMAT=pretty",
                "SYNAPSE_LOG_COLOR=never",
                "SYNAPSE_QUIET_DIAGNOSTICS_ACCESS_LOGS=false",
                "SYNAPSE_LOG_LLM_DETAILS=true",
            ]
        )
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.log_format == "pretty"
    assert settings.log_color == "never"
    assert settings.quiet_diagnostics_access_logs is False
    assert settings.log_llm_details is True


def test_load_settings_prefers_yaml_codex_command(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text(
        "\n".join(
            [
                "SYNAPSE_CODEX_EXECUTOR_ENABLED=true",
                "SYNAPSE_CODEX_COMMAND=/env/codex",
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
                "  codex_command: /yaml/codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.codex_executor_enabled is True
    assert settings.codex_command == "/yaml/codex"


def test_load_settings_falls_back_to_legacy_env_codex_command(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text(
        "\n".join(
            [
                "SYNAPSE_CODEX_EXECUTOR_ENABLED=true",
                "SYNAPSE_CODEX_COMMAND=/env/codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.codex_executor_enabled is True
    assert settings.codex_command == "/env/codex"
