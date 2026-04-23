from __future__ import annotations

from pathlib import Path

import pytest

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
        "SYNAPSE_ACPX_EXECUTOR_ENABLED",
        "SYNAPSE_ACPX_COMMAND",
        "SYNAPSE_ACPX_AGENT",
        "SYNAPSE_ACPX_PERMISSION_MODE",
        "SYNAPSE_ACPX_NON_INTERACTIVE_PERMISSIONS",
        "SYNAPSE_ACPX_TIMEOUT_SECONDS",
        "SYNAPSE_CODEX_EXECUTOR_ENABLED",
        "SYNAPSE_CODEX_COMMAND",
        "SYNAPSE_CODEX_BLOCKED_WAIT_TIMEOUT_SECONDS",
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


def test_load_settings_reads_acpx_executor_config_from_env(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text(
        "\n".join(
            [
                "SYNAPSE_ACPX_EXECUTOR_ENABLED=true",
                "SYNAPSE_ACPX_COMMAND=/usr/local/bin/acpx",
                "SYNAPSE_ACPX_AGENT=claude",
                "SYNAPSE_ACPX_PERMISSION_MODE=approve-reads",
                "SYNAPSE_ACPX_NON_INTERACTIVE_PERMISSIONS=fail",
                "SYNAPSE_ACPX_TIMEOUT_SECONDS=90",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.acpx_executor_enabled is True
    assert settings.acpx_command == "/usr/local/bin/acpx"
    assert settings.acpx_agent == "claude"
    assert settings.acpx_permission_mode == "approve-reads"
    assert settings.acpx_non_interactive_permissions == "fail"
    assert settings.acpx_timeout_seconds == 90.0


def test_load_settings_prefers_yaml_acpx_command_and_agent(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text(
        "\n".join(
            [
                "SYNAPSE_ACPX_EXECUTOR_ENABLED=true",
                "SYNAPSE_ACPX_COMMAND=/env/acpx",
                "SYNAPSE_ACPX_AGENT=claude",
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
                "  acpx_command: /yaml/acpx",
                "  acpx_agent: openclaw",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.acpx_executor_enabled is True
    assert settings.acpx_command == "/yaml/acpx"
    assert settings.acpx_agent == "openclaw"


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


def test_load_settings_reads_codex_blocked_wait_timeout(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text(
        "SYNAPSE_CODEX_BLOCKED_WAIT_TIMEOUT_SECONDS=42\n",
        encoding="utf-8",
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.codex_blocked_wait_timeout_seconds == 42.0


def test_parse_string_list_uses_field_name_in_error():
    with pytest.raises(RuntimeError, match="runtime.detached_executor_types must be a list of strings."):
        config_module._parse_string_list([1], field_name="runtime.detached_executor_types")


def test_load_settings_always_enables_detached_executors_with_supported_types(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.yaml"
    clear_runtime_env(monkeypatch)
    env_file.write_text("", encoding="utf-8")
    config_file.write_text(
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  detached_executor_enabled: false",
                "  detached_executor_types:",
                "    - codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    configure_runtime_paths(monkeypatch, env_file=env_file, config_file=config_file)

    settings = config_module.load_settings()

    assert settings.detached_executor_enabled is True
    assert settings.detached_executor_types == config_module.SUPPORTED_DETACHED_EXECUTOR_TYPES
