from __future__ import annotations

from pathlib import Path

from synopse.runtime import config as config_module


def test_load_settings_reads_openai_config(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "SYNOPSE_OPENAI_MODEL=gpt-4.1-mini",
                "SYNOPSE_OPENAI_TIMEOUT_SECONDS=45",
            ]
        )
    )
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)

    settings = config_module.load_settings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_timeout_seconds == 45.0


def test_load_settings_reads_log_output_config(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "SYNOPSE_LOG_FORMAT=pretty",
                "SYNOPSE_LOG_COLOR=never",
                "SYNOPSE_QUIET_DIAGNOSTICS_ACCESS_LOGS=false",
                "SYNOPSE_LOG_LLM_DETAILS=true",
            ]
        )
    )
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)

    settings = config_module.load_settings()

    assert settings.log_format == "pretty"
    assert settings.log_color == "never"
    assert settings.quiet_diagnostics_access_logs is False
    assert settings.log_llm_details is True


def test_load_settings_reads_acpx_executor_config(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "SYNOPSE_ACPX_EXECUTOR_ENABLED=true",
                "SYNOPSE_ACPX_COMMAND=/usr/local/bin/acpx",
                "SYNOPSE_ACPX_AGENT=claude",
                "SYNOPSE_ACPX_PERMISSION_MODE=approve-reads",
                "SYNOPSE_ACPX_NON_INTERACTIVE_PERMISSIONS=fail",
                "SYNOPSE_ACPX_TIMEOUT_SECONDS=90",
            ]
        )
    )
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)

    settings = config_module.load_settings()

    assert settings.acpx_executor_enabled is True
    assert settings.acpx_command == "/usr/local/bin/acpx"
    assert settings.acpx_agent == "claude"
    assert settings.acpx_permission_mode == "approve-reads"
    assert settings.acpx_non_interactive_permissions == "fail"
    assert settings.acpx_timeout_seconds == 90.0
