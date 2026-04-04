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
    assert settings.default_executor_id is None


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


def test_load_settings_reads_codex_executor_configuration(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "SYNOPSE_CODEX_EXECUTOR_ENABLED=true\n"
        "SYNOPSE_CODEX_EXECUTOR_ID=codex_executor\n"
        "SYNOPSE_CODEX_CLI_PATH=/usr/local/bin/codex\n"
        "SYNOPSE_CODEX_WORKDIR=/tmp/workdir\n"
        "SYNOPSE_CODEX_MODEL=gpt-test\n"
        "SYNOPSE_CODEX_TIMEOUT_SECONDS=90\n"
        "SYNOPSE_CODEX_SANDBOX=read-only\n"
        "SYNOPSE_CODEX_APPROVAL_POLICY=never\n"
    )

    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.delenv("SYNOPSE_CODEX_EXECUTOR_ENABLED", raising=False)
    monkeypatch.delenv("SYNOPSE_CODEX_EXECUTOR_ID", raising=False)
    monkeypatch.delenv("SYNOPSE_CODEX_CLI_PATH", raising=False)
    monkeypatch.delenv("SYNOPSE_CODEX_WORKDIR", raising=False)
    monkeypatch.delenv("SYNOPSE_CODEX_MODEL", raising=False)
    monkeypatch.delenv("SYNOPSE_CODEX_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SYNOPSE_CODEX_SANDBOX", raising=False)
    monkeypatch.delenv("SYNOPSE_CODEX_APPROVAL_POLICY", raising=False)

    settings = config_module.load_settings()

    assert settings.codex_executor_enabled is True
    assert settings.codex_executor_id == "codex_executor"
    assert settings.codex_cli_path == "/usr/local/bin/codex"
    assert settings.codex_workdir == "/tmp/workdir"
    assert settings.codex_model == "gpt-test"
    assert settings.codex_timeout_seconds == 90.0
    assert settings.codex_sandbox == "read-only"
    assert settings.codex_approval_policy == "never"


def test_load_settings_reads_explicit_default_executor(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("SYNOPSE_DEFAULT_EXECUTOR_ID=mock_executor\n")

    monkeypatch.setattr(config_module, "LOCAL_ENV_FILE", env_file)
    monkeypatch.delenv("SYNOPSE_DEFAULT_EXECUTOR_ID", raising=False)

    settings = config_module.load_settings()

    assert settings.default_executor_id == "mock_executor"
