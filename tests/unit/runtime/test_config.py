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
