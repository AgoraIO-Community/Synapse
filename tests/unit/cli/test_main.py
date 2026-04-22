from __future__ import annotations

import builtins
import importlib
from pathlib import Path
import re

cli_main = importlib.import_module("synapse.cli.main")


class FakeCompletedProcess:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode


def test_frontend_tool_prefers_bun(monkeypatch):
    monkeypatch.setattr(cli_main.shutil, "which", lambda name: f"/usr/bin/{name}" if name in {"bun", "npm"} else None)

    assert cli_main.preferred_frontend_tool() == "bun"


def test_frontend_tool_falls_back_to_npm(monkeypatch):
    monkeypatch.setattr(cli_main.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)

    assert cli_main.preferred_frontend_tool() == "npm"


def configure_repo_paths(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(cli_main, "ROOT", root)
    monkeypatch.setattr(cli_main, "FRONTEND", root / "src" / "synapse" / "ui")
    monkeypatch.setattr(cli_main, "VENV_DIR", root / ".venv")
    monkeypatch.setattr(cli_main, "ENV_LOCAL", root / ".synapse" / ".env")


def force_yaml_fallback(monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def test_setup_interactive_updates_env_file(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / ".env").write_text(
        "SYNAPSE_OPENAI_MODEL=gpt-4.1-mini\nEXTRA_FLAG=keep-me\n",
        encoding="utf-8",
    )

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main.getpass, "getpass", lambda _prompt: "sk-test")
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    assert cli_main.main(["setup"]) == 0

    configured = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test" in configured
    assert "SYNAPSE_OPENAI_MODEL=gpt-4.1-mini" in configured
    assert configured.strip().endswith("EXTRA_FLAG=keep-me")

    configured_runtime = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "detached_executor_enabled: false" in configured_runtime
    assert "detached_executor_types" not in configured_runtime
    assert "executor_host:" in configured_runtime
    assert "executors: {}" in configured_runtime
    assert "host_token" not in configured_runtime
    assert "heartbeat_seconds" not in configured_runtime
    assert re.search(r"host_id: host-[0-9a-f]{8}", configured_runtime)


def test_setup_interactive_enables_detached_executors(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main.getpass, "getpass", lambda _prompt: "sk-test")
    responses = iter(["yes", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli_main.main(["setup"]) == 0

    configured_runtime = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "detached_executor_enabled: true" in configured_runtime
    assert "detached_executor_types:" in configured_runtime
    assert "- codex" in configured_runtime


def test_executor_setup_uses_detected_codex_command_default(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  detached_executor_enabled: true",
                "  detached_executor_types:",
                "    - codex",
                "host:",
                "  enabled: false",
                "  host: 0.0.0.0",
                "  port: 8010",
                '  public_base_url: "http://127.0.0.1:8010"',
                '  synapse_base_url: "http://127.0.0.1:8000"',
                "  enabled_gateways: []",
                "gateways: {}",
                "executor_host:",
                "  enabled: false",
                '  synapse_base_url: "http://127.0.0.1:8000"',
                "  host_id: default-host",
                "  enabled_executors: []",
                "executors: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main, "_detected_codex_command", lambda: "/detected/codex")
    monkeypatch.setattr(
        cli_main,
        "_codex_command_available",
        lambda command: command == "/detected/codex",
    )
    responses = iter(["", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli_main.main(["executor", "setup"]) == 0

    configured_runtime = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "detached_executor_enabled: true" in configured_runtime
    assert "detached_executor_types:" in configured_runtime
    assert "executor_host:" in configured_runtime
    assert "command: /detected/codex" in configured_runtime
    assert "host_token" not in configured_runtime
    assert "heartbeat_seconds" not in configured_runtime
    assert re.search(r"host_id: host-[0-9a-f]{8}", configured_runtime)


def test_executor_setup_migrates_legacy_codex_command_over_detected_default(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / ".env").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-existing",
                "SYNAPSE_CODEX_EXECUTOR_ENABLED=true",
                "SYNAPSE_CODEX_COMMAND=/legacy/codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  detached_executor_enabled: true",
                "  detached_executor_types:",
                "    - codex",
                "host:",
                "  enabled: false",
                "  host: 0.0.0.0",
                "  port: 8010",
                '  public_base_url: "http://127.0.0.1:8010"',
                '  synapse_base_url: "http://127.0.0.1:8000"',
                "  enabled_gateways: []",
                "gateways: {}",
                "executor_host:",
                "  enabled: false",
                '  synapse_base_url: "http://127.0.0.1:8000"',
                "  host_id: default-host",
                "  enabled_executors: []",
                "executors: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main, "_detected_codex_command", lambda: "/detected/codex")
    monkeypatch.setattr(
        cli_main,
        "_codex_command_available",
        lambda command: command in {"/legacy/codex", "/detected/codex"},
    )
    responses = iter(["", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli_main.main(["executor", "setup"]) == 0

    configured_env = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    configured_runtime = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "command: /legacy/codex" in configured_runtime
    assert "command: /detected/codex" not in configured_runtime
    assert "SYNAPSE_CODEX_COMMAND=/legacy/codex" not in configured_env
    assert "host_token" not in configured_runtime
    assert "heartbeat_seconds" not in configured_runtime


def test_gateway_setup_writes_gateway_module_env(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main, "list_available_gateway_modules", lambda: ["agora-convoai"])
    secret_responses = iter(["app-cert"])
    monkeypatch.setattr(cli_main.getpass, "getpass", lambda _prompt: next(secret_responses))

    allowed_empty_prompts = {
        "Configure gateway host [Y/n]: ",
        "Select gateways [1]: ",
        "Gateway host [0.0.0.0]: ",
        "Gateway port [8010]: ",
        "Gateway public base URL [http://127.0.0.1:8010]: ",
        "Synapse API base URL for gateway callbacks [http://127.0.0.1:8000]: ",
        "ASR credential mode [managed]: ",
        "ASR model [nova-3]: ",
        "ASR language [en-US]: ",
        "TTS vendor [minimax]: ",
        "TTS model [speech_2_6_turbo]: ",
        "TTS voice [English_magnetic_voiced_man]: ",
    }

    def fake_input(prompt: str) -> str:
        if prompt.startswith("Agora App ID"):
            return "agora-app"
        if prompt in allowed_empty_prompts:
            return ""
        raise AssertionError(f"Unexpected prompt: {prompt}")

    monkeypatch.setattr("builtins.input", fake_input)

    assert cli_main.main(["gateway", "setup"]) == 0

    configured = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "AGORA_APP_ID=agora-app" in configured
    assert "AGORA_APP_CERTIFICATE=app-cert" in configured

    gateway_config = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "runtime: {}" in gateway_config
    assert "enabled_gateways:" in gateway_config
    assert "- agora-convoai" in gateway_config
    assert "app_id: $AGORA_APP_ID" in gateway_config
    assert "convoai_area: US" in gateway_config
    assert "credential_mode: managed" in gateway_config
    assert "vendor: minimax" in gateway_config
    assert "voice: English_magnetic_voiced_man" in gateway_config


def test_gateway_setup_decline_disables_existing_gateway_config(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  codex_command: /existing/codex",
                "host:",
                "  enabled: true",
                "  enabled_gateways:",
                "    - agora-convoai",
                "gateways:",
                "  agora-convoai:",
                "    app_id: $AGORA_APP_ID",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "no")

    assert cli_main.main(["gateway", "setup"]) == 0

    configured = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "codex_command: /existing/codex" in configured
    assert "enabled: false" in configured
    assert "enabled_gateways:" in configured


def test_gateway_setup_reads_existing_legacy_empty_gateways_config_with_yaml_fallback(
    monkeypatch,
    tmp_path: Path,
):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "host:",
                "  enabled: false",
                "  host: 0.0.0.0",
                "  port: 8010",
                '  public_base_url: "http://127.0.0.1:8010"',
                '  synapse_base_url: "http://127.0.0.1:8000"',
                "  enabled_gateways:",
                "gateways:",
                "  {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main, "list_available_gateway_modules", lambda: ["agora-convoai"])
    force_yaml_fallback(monkeypatch)

    secret_responses = iter(["app-cert"])
    monkeypatch.setattr(cli_main.getpass, "getpass", lambda _prompt: next(secret_responses))

    allowed_empty_prompts = {
        "Select gateways [1]: ",
        "Gateway host [0.0.0.0]: ",
        "Gateway port [8010]: ",
        "Gateway public base URL [http://127.0.0.1:8010]: ",
        "Synapse API base URL for gateway callbacks [http://127.0.0.1:8000]: ",
        "ASR credential mode [managed]: ",
        "ASR model [nova-3]: ",
        "ASR language [en-US]: ",
        "TTS vendor [minimax]: ",
        "TTS model [speech_2_6_turbo]: ",
        "TTS voice [English_magnetic_voiced_man]: ",
    }

    def fake_input(prompt: str) -> str:
        if prompt in {"Configure gateway host [y/N]: ", "Configure gateway host [Y/n]: "}:
            return "y"
        if prompt.startswith("Agora App ID"):
            return "agora-app"
        if prompt in allowed_empty_prompts:
            return ""
        raise AssertionError(f"Unexpected prompt: {prompt}")

    monkeypatch.setattr("builtins.input", fake_input)

    assert cli_main.main(["gateway", "setup"]) == 0

    configured = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "gateways:\n  {}" not in configured
    assert "gateways:" in configured
    assert "app_id: $AGORA_APP_ID" in configured


def test_gateway_listing_and_settings_do_not_require_fastapi(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / ".env").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "host:",
                "  enabled: true",
                "  enabled_gateways:",
                "    - agora-convoai",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    configure_repo_paths(monkeypatch, root)

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("fastapi"):
            raise ModuleNotFoundError("No module named 'fastapi'")
        if name.startswith("dotenv"):
            raise ModuleNotFoundError("No module named 'dotenv'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert cli_main.list_available_gateway_modules() == ["agora-convoai"]
    settings = cli_main.load_gateway_settings()
    assert settings.enabled is True
    assert settings.enabled_gateways == ["agora-convoai"]


def test_setup_non_interactive_uses_existing_and_env(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

    assert cli_main.main(["setup", "--non-interactive"]) == 0

    configured = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-env" in configured
    assert "SYNAPSE_CODEX_EXECUTOR_ENABLED" not in configured
    assert "SYNAPSE_CODEX_COMMAND" not in configured
    configured_runtime = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "runtime: {}" in configured_runtime
    assert "executor_host:" in configured_runtime
    assert "executors: {}" in configured_runtime


def test_executor_setup_migrates_legacy_codex_command_to_config(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / ".env").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "SYNAPSE_CODEX_EXECUTOR_ENABLED=true",
                "SYNAPSE_CODEX_COMMAND=/legacy/codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  detached_executor_enabled: true",
                "  detached_executor_types:",
                "    - codex",
                "host:",
                "  enabled: false",
                "  host: 0.0.0.0",
                "  port: 8010",
                '  public_base_url: "http://127.0.0.1:8010"',
                '  synapse_base_url: "http://127.0.0.1:8000"',
                "  enabled_gateways: []",
                "gateways: {}",
                "executor_host:",
                "  enabled: false",
                '  synapse_base_url: "http://127.0.0.1:8000"',
                "  host_id: default-host",
                "  enabled_executors: []",
                "executors: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main, "_codex_command_available", lambda command: command == "/legacy/codex")
    responses = iter(["", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli_main.main(["executor", "setup"]) == 0

    configured_env = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "SYNAPSE_CODEX_COMMAND=/legacy/codex" not in configured_env
    assert "SYNAPSE_CODEX_EXECUTOR_ENABLED=true" not in configured_env

    configured_runtime = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "command: /legacy/codex" in configured_runtime
    assert "host_token" not in configured_runtime
    assert "heartbeat_seconds" not in configured_runtime
    assert re.search(r"host_id: host-[0-9a-f]{8}", configured_runtime)


def test_executor_setup_requires_detached_executor_runtime_config(monkeypatch, tmp_path: Path, capsys):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)

    assert cli_main.main(["executor", "setup"]) == 1
    assert "Detached executors are disabled. Run `./synapse setup` first." in capsys.readouterr().err


def test_setup_non_interactive_tolerates_malformed_existing_config(monkeypatch, tmp_path: Path, capsys):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / ".env").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
                "SYNAPSE_CODEX_EXECUTOR_ENABLED=true",
                "SYNAPSE_CODEX_COMMAND=/legacy/codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".synapse" / "config.yaml").write_text("version: [\n", encoding="utf-8")

    configure_repo_paths(monkeypatch, root)

    assert cli_main.main(["setup", "--non-interactive"]) == 0

    output = capsys.readouterr().out
    assert "ignoring invalid existing config" in output

    configured_runtime = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "runtime:" in configured_runtime
    assert "executor_host:" in configured_runtime
    assert "executors: {}" in configured_runtime


def test_setup_non_interactive_requires_openai(monkeypatch, tmp_path: Path, capsys):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)

    configure_repo_paths(monkeypatch, root)

    assert cli_main.main(["setup", "--non-interactive"]) == 1
    assert "OPENAI_API_KEY is required for non-interactive setup" in capsys.readouterr().err


def test_setup_bootstrap_defaults_creates_env_and_gateway_config(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-shell-secret")
    monkeypatch.setenv("AGORA_APP_ID", "agora-shell-app")
    monkeypatch.setenv("SYNAPSE_CODEX_EXECUTOR_ENABLED", "true")
    monkeypatch.setenv("SYNAPSE_CODEX_COMMAND", "/shell/codex")

    assert cli_main.main(["setup", "--bootstrap-defaults"]) == 0

    configured_env = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=\n" in configured_env
    assert "SYNAPSE_OPENAI_MODEL=gpt-4o-mini" in configured_env
    assert "sk-shell-secret" not in configured_env
    assert "agora-shell-app" not in configured_env
    assert "/shell/codex" not in configured_env

    configured_gateway = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "runtime: {}" in configured_gateway
    assert "enabled: false" in configured_gateway
    assert 'public_base_url: "http://127.0.0.1:8010"' in configured_gateway
    assert "enabled_gateways: []" in configured_gateway
    assert "gateways: {}" in configured_gateway
    assert "gateways:\n  {}" not in configured_gateway
    assert "executor_host:" in configured_gateway
    assert "enabled_executors: []" in configured_gateway
    assert "host_token" not in configured_gateway
    assert "heartbeat_seconds" not in configured_gateway
    assert re.search(r"host_id: host-[0-9a-f]{8}", configured_gateway)
    assert "executors: {}" in configured_gateway


def test_setup_bootstrap_defaults_preserves_existing_files(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / ".env").write_text("OPENAI_API_KEY=existing\n", encoding="utf-8")
    (root / ".synapse" / "config.yaml").write_text("version: 1\n", encoding="utf-8")

    configure_repo_paths(monkeypatch, root)

    assert cli_main.main(["setup", "--bootstrap-defaults"]) == 0
    assert (root / ".synapse" / ".env").read_text(encoding="utf-8") == "OPENAI_API_KEY=existing\n"
    assert (root / ".synapse" / "config.yaml").read_text(encoding="utf-8") == "version: 1\n"


def test_setup_bootstrap_defaults_ignores_malformed_codex_shell_env(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setenv("SYNAPSE_CODEX_EXECUTOR_ENABLED", "not-a-bool")

    assert cli_main.main(["setup", "--bootstrap-defaults"]) == 0

    configured_env = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "SYNAPSE_CODEX_EXECUTOR_ENABLED" not in configured_env


def test_backend_requires_setup(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cli_main, "VENV_DIR", tmp_path / ".venv")

    assert cli_main.main(["backend"]) == 1


def test_doctor_reads_openai_key_from_env_file(monkeypatch, tmp_path: Path, capsys):
    env_local = tmp_path / ".synapse" / ".env"
    env_local.parent.mkdir(parents=True, exist_ok=True)
    env_local.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    configure_repo_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_main, "report_port", lambda _port: True)
    monkeypatch.setattr(cli_main, "report_command", lambda _name, required=True: True)

    assert cli_main.main(["doctor"]) == 0
    assert "[ok] env: OPENAI_API_KEY" in capsys.readouterr().out


def test_doctor_points_to_install_and_setup(monkeypatch, tmp_path: Path, capsys):
    configure_repo_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_main, "report_port", lambda _port: True)
    monkeypatch.setattr(cli_main, "report_command", lambda _name, required=True: True)

    assert cli_main.main(["doctor"]) == 1
    output = capsys.readouterr().out
    assert "[missing] virtualenv: run ./install.sh" in output
    assert "[missing] env file: run ./synapse setup" in output


def test_report_port_tolerates_permission_error(monkeypatch, capsys):
    class DeniedSocket:
        def bind(self, _address):
            raise PermissionError

        def close(self):
            return None

    monkeypatch.setattr(cli_main.socket, "socket", lambda: DeniedSocket())

    assert cli_main.report_port(8000) is True
    assert "[warn] port 8000 could not be checked in this environment" in capsys.readouterr().out


def test_dev_uses_repo_venv_and_frontend_command(monkeypatch, tmp_path: Path):
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    class FakeProcess:
        def __init__(self, returncode: int | None = None):
            self._returncode = returncode

        def poll(self):
            return self._returncode

        def terminate(self):
            self._returncode = 0

        def kill(self):
            self._returncode = -9

    spawned: list[tuple[list[str], Path]] = []
    processes = [FakeProcess(0), FakeProcess(None), FakeProcess(None)]

    def fake_popen(cmd: list[str], cwd: Path):
        spawned.append((cmd, cwd))
        return processes[len(spawned) - 1]

    configure_repo_paths(monkeypatch, tmp_path)
    (tmp_path / ".synapse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".synapse" / ".env").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "host:",
                "  enabled: true",
                "  port: 8010",
                "  public_base_url: http://127.0.0.1:8010",
                "  enabled_gateways:",
                "    - agora-convoai",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_main.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "frontend_dev_command", lambda host, port: ["npm", "run", "dev", "--", "--host", host, "--port", str(port)])

    assert cli_main.main(["dev"]) == 0
    assert spawned[0][0][:4] == [str(venv_python), "-m", "uvicorn", "synapse.api.app:app"]
    assert spawned[1][0] == ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
    assert spawned[2][0][:4] == [str(venv_python), "-m", "uvicorn", "synapse.gateway_host.app:app"]


def test_start_uses_edge_transport_and_internal_upstreams(monkeypatch, tmp_path: Path):
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")
    dist_dir = tmp_path / "src" / "synapse" / "ui" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")

    configure_repo_paths(monkeypatch, tmp_path)
    (tmp_path / ".synapse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".synapse" / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    (tmp_path / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "host:",
                "  enabled: true",
                "  host: 0.0.0.0",
                "  port: 8010",
                '  public_base_url: "http://127.0.0.1:8010"',
                "  enabled_gateways:",
                "    - agora-convoai",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_run_managed_processes(commands):
        captured["commands"] = commands
        return 0

    monkeypatch.setattr(cli_main, "run_managed_processes", fake_run_managed_processes)

    assert cli_main.main(["start"]) == 0

    commands = captured["commands"]
    assert commands[0][0] == "backend"
    assert commands[0][1][:4] == [str(venv_python), "-m", "uvicorn", "synapse.api.app:app"]
    assert commands[0][1][-4:] == ["--host", "127.0.0.1", "--port", "8001"]
    assert commands[1] == (
        "edge",
        [
            str(venv_python),
            "-m",
            "synapse.edge",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--backend-base-url",
            "http://127.0.0.1:8001",
            "--frontend-dist",
            str(dist_dir),
            "--gateway-base-url",
            "http://127.0.0.1:8010",
        ],
        tmp_path,
    )
    assert commands[2][0] == "gateway"
    assert commands[2][1][-4:] == ["--host", "127.0.0.1", "--port", "8010"]


def configure_service_environment(monkeypatch, tmp_path: Path) -> None:
    configure_repo_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_main.sys, "platform", "linux")
    monkeypatch.setattr(cli_main.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli_main.getpass, "getuser", lambda: "deploy")
    monkeypatch.setattr(
        cli_main.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"sudo", "systemctl", "bun"} else None,
    )


def configure_root_service_environment(monkeypatch, tmp_path: Path) -> None:
    configure_repo_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_main.sys, "platform", "linux")
    monkeypatch.setattr(cli_main.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli_main.getpass, "getuser", lambda: "root")
    monkeypatch.setattr(
        cli_main.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"systemctl", "bun"} else None,
    )


def test_service_install_bootstraps_runtime_and_enables_unit(monkeypatch, tmp_path: Path, capsys):
    configure_service_environment(monkeypatch, tmp_path)

    commands: list[tuple[list[str], Path]] = []

    def fake_run_checked(cmd: list[str], cwd: Path) -> int:
        commands.append((cmd, cwd))
        if len(cmd) >= 3 and cmd[1:3] == ["-m", "venv"]:
            venv_python = tmp_path / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(cli_main, "run_checked", fake_run_checked)

    assert cli_main.main(["service", "install", "--host", "0.0.0.0", "--port", "9000"]) == 0

    venv_python = tmp_path / ".venv" / "bin" / "python"
    assert commands[0] == ([cli_main.sys.executable, "-m", "venv", str(tmp_path / ".venv")], tmp_path)
    assert commands[1] == ([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], tmp_path)
    assert commands[2] == ([str(venv_python), "-m", "pip", "install", "-e", "."], tmp_path)
    assert commands[3] == (["bun", "install"], tmp_path / "src" / "synapse" / "ui")
    assert commands[4] == (["bun", "run", "build"], tmp_path / "src" / "synapse" / "ui")
    assert commands[5][0][0:8] == ["sudo", "install", "-o", "root", "-g", "root", "-m", "0644"]
    assert commands[5][0][-1] == str(cli_main.service_unit_path())
    assert commands[6] == (["sudo", "systemctl", "daemon-reload"], tmp_path)
    assert commands[7] == (["sudo", "systemctl", "enable", "synapse.service"], tmp_path)
    assert (tmp_path / ".synapse" / ".env").exists()
    assert (tmp_path / ".synapse" / "config.yaml").exists()
    assert "[warn] env: OPENAI_API_KEY is not configured" in capsys.readouterr().out


def test_service_install_skips_venv_creation_when_existing(monkeypatch, tmp_path: Path):
    configure_service_environment(monkeypatch, tmp_path)
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")
    (tmp_path / ".synapse").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".synapse" / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

    commands: list[list[str]] = []
    monkeypatch.setattr(cli_main, "run_checked", lambda cmd, cwd: commands.append(cmd) or 0)

    assert cli_main.main(["service", "install"]) == 0
    assert all(cmd[1:3] != ["-m", "venv"] for cmd in commands if len(cmd) >= 3)
    assert commands[0] == [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"]
    assert ["bun", "install"] in commands
    assert ["bun", "run", "build"] in commands


def test_service_install_allows_root_and_uses_direct_systemctl(monkeypatch, tmp_path: Path, capsys):
    configure_root_service_environment(monkeypatch, tmp_path)

    commands: list[tuple[list[str], Path]] = []

    def fake_run_checked(cmd: list[str], cwd: Path) -> int:
        commands.append((cmd, cwd))
        if len(cmd) >= 3 and cmd[1:3] == ["-m", "venv"]:
            venv_python = tmp_path / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("", encoding="utf-8")
        return 0

    monkeypatch.setattr(cli_main, "run_checked", fake_run_checked)

    assert cli_main.main(["service", "install", "--host", "0.0.0.0", "--port", "9000"]) == 0

    venv_python = tmp_path / ".venv" / "bin" / "python"
    assert commands[0] == ([cli_main.sys.executable, "-m", "venv", str(tmp_path / ".venv")], tmp_path)
    assert commands[1] == ([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], tmp_path)
    assert commands[2] == ([str(venv_python), "-m", "pip", "install", "-e", "."], tmp_path)
    assert commands[3] == (["bun", "install"], tmp_path / "src" / "synapse" / "ui")
    assert commands[4] == (["bun", "run", "build"], tmp_path / "src" / "synapse" / "ui")
    assert commands[5][0][0:7] == ["install", "-o", "root", "-g", "root", "-m", "0644"]
    assert commands[5][0][-1] == str(cli_main.service_unit_path())
    assert commands[6] == (["systemctl", "daemon-reload"], tmp_path)
    assert commands[7] == (["systemctl", "enable", "synapse.service"], tmp_path)
    assert (tmp_path / ".synapse" / ".env").exists()
    assert (tmp_path / ".synapse" / "config.yaml").exists()
    assert "[warn] env: OPENAI_API_KEY is not configured" in capsys.readouterr().out


def test_service_install_requires_systemctl(monkeypatch, tmp_path: Path, capsys):
    configure_repo_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_main.sys, "platform", "linux")
    monkeypatch.setattr(cli_main.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli_main.shutil, "which", lambda _name: None)

    assert cli_main.main(["service", "install"]) == 1
    assert "systemctl is required" in capsys.readouterr().err


def test_service_install_rejects_non_linux(monkeypatch, tmp_path: Path, capsys):
    configure_repo_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(cli_main.sys, "platform", "darwin")
    monkeypatch.setattr(cli_main.os, "geteuid", lambda: 1000)

    assert cli_main.main(["service", "install"]) == 1
    assert "supports Linux/systemd hosts only" in capsys.readouterr().err


def test_render_service_unit_includes_expected_values():
    unit = cli_main.render_service_unit(
        user="deploy",
        home=Path("/home/deploy"),
        workdir=Path("/srv/synapse"),
        venv_python=Path("/srv/synapse/.venv/bin/python"),
        host="0.0.0.0",
        public_port=8000,
        backend_port=8001,
    )

    assert "User=deploy" in unit
    assert "WorkingDirectory=/srv/synapse" in unit
    assert 'Environment="HOME=/home/deploy"' in unit
    assert 'Environment="PATH=/srv/synapse/.venv/bin:/home/deploy/.local/bin:/home/deploy/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' in unit
    assert (
        "ExecStart=/srv/synapse/.venv/bin/python -m synapse start --host 0.0.0.0 --port 8000 --backend-port 8001"
        in unit
    )
    assert "Restart=on-failure" in unit
    assert "WantedBy=multi-user.target" in unit


def test_render_service_unit_supports_root_values():
    unit = cli_main.render_service_unit(
        user="root",
        home=Path("/root"),
        workdir=Path("/srv/synapse"),
        venv_python=Path("/srv/synapse/.venv/bin/python"),
        host="0.0.0.0",
        public_port=8000,
        backend_port=8001,
    )

    assert "User=root" in unit
    assert 'Environment="HOME=/root"' in unit
    assert 'Environment="PATH=/srv/synapse/.venv/bin:/root/.local/bin:/root/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' in unit


def test_start_requires_production_frontend_build(monkeypatch, tmp_path: Path, capsys):
    configure_repo_paths(monkeypatch, tmp_path)
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    assert cli_main.main(["start"]) == 1
    assert "Frontend production build is missing" in capsys.readouterr().err


def test_service_lifecycle_commands_use_sudo(monkeypatch, tmp_path: Path):
    configure_service_environment(monkeypatch, tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(cli_main, "run_checked", lambda cmd, cwd: commands.append(cmd) or 0)

    assert cli_main.main(["service", "start"]) == 0
    assert cli_main.main(["service", "stop"]) == 0
    assert cli_main.main(["service", "restart"]) == 0

    assert commands == [
        ["sudo", "systemctl", "start", "synapse.service"],
        ["sudo", "systemctl", "stop", "synapse.service"],
        ["sudo", "systemctl", "restart", "synapse.service"],
    ]
