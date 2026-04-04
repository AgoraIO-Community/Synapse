from pathlib import Path

from runtime.infrastructure import config as config_module


def test_load_settings_reads_values_from_local_env_file(
    monkeypatch,
    tmp_path: Path,
):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "OPENAI_API_KEY=file-key\n"
        "SYNOPSE_OPENAI_MODEL=gpt-test\n"
        "SYNOPSE_OPENAI_TIMEOUT_SECONDS=45\n"
    )

    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SYNOPSE_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("SYNOPSE_OPENAI_TIMEOUT_SECONDS", raising=False)

    settings = config_module.load_settings()

    assert settings.openai_api_key == "file-key"
    assert settings.openai_model == "gpt-test"
    assert settings.openai_timeout_seconds == 45.0


def test_shell_env_overrides_local_env_file(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "OPENAI_API_KEY=file-key\n"
        "SYNOPSE_OPENAI_MODEL=file-model\n"
    )

    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")
    monkeypatch.setenv("SYNOPSE_OPENAI_MODEL", "shell-model")

    settings = config_module.load_settings()

    assert settings.openai_api_key == "shell-key"
    assert settings.openai_model == "shell-model"
