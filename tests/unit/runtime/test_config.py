from __future__ import annotations

from pathlib import Path

from synapse.runtime import config as config_module


def test_load_settings_reads_openai_config(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "SYNAPSE_OPENAI_MODEL=gpt-4.1-mini",
                "SYNAPSE_OPENAI_TIMEOUT_SECONDS=45",
            ]
        )
    )
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)

    settings = config_module.load_settings()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_timeout_seconds == 45.0


def test_load_settings_reads_log_output_config(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
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
    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)

    settings = config_module.load_settings()

    assert settings.log_format == "pretty"
    assert settings.log_color == "never"
    assert settings.quiet_diagnostics_access_logs is False
    assert settings.log_llm_details is True
