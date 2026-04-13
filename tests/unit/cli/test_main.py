from __future__ import annotations

import builtins
import importlib
from pathlib import Path

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


def write_template(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=your_openai_api_key_here",
                "SYNAPSE_OPENAI_MODEL=gpt-4o-mini",
                "SYNAPSE_OPENAI_TIMEOUT_SECONDS=30",
                "# SYNAPSE_OPENAI_BASE_URL=",
                "SYNAPSE_CODEX_EXECUTOR_ENABLED=false",
                "# SYNAPSE_CODEX_COMMAND=codex",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def configure_repo_paths(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(cli_main, "ROOT", root)
    monkeypatch.setattr(cli_main, "FRONTEND", root / "src" / "synapse" / "ui")
    monkeypatch.setattr(cli_main, "VENV_DIR", root / ".venv")
    monkeypatch.setattr(cli_main, "ENV_EXAMPLE", root / ".env.example")
    monkeypatch.setattr(cli_main, "ENV_LOCAL", root / ".synapse" / ".env")


def test_setup_interactive_updates_env_file(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    write_template(root / ".env.example")
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / ".env").write_text(
        "SYNAPSE_OPENAI_MODEL=gpt-4.1-mini\nEXTRA_FLAG=keep-me\n",
        encoding="utf-8",
    )

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main.getpass, "getpass", lambda _prompt: "sk-test")
    responses = iter(["yes", "/custom/codex", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))
    monkeypatch.setattr(cli_main, "_codex_command_available", lambda command: command == "/custom/codex")

    assert cli_main.main(["setup"]) == 0

    configured = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test" in configured
    assert "SYNAPSE_OPENAI_MODEL=gpt-4.1-mini" in configured
    assert "SYNAPSE_CODEX_EXECUTOR_ENABLED=true" in configured
    assert "SYNAPSE_CODEX_COMMAND=/custom/codex" in configured
    assert configured.strip().endswith("EXTRA_FLAG=keep-me")


def test_gateway_setup_writes_gateway_module_env(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    write_template(root / ".env.example")

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    monkeypatch.setattr(cli_main, "list_available_gateway_modules", lambda: ["agora-convoai"])
    secret_responses = iter(["app-cert"])
    monkeypatch.setattr(cli_main.getpass, "getpass", lambda _prompt: next(secret_responses))

    def fake_input(prompt: str) -> str:
        if prompt.startswith("Agora App ID"):
            return "agora-app"
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    assert cli_main.main(["gateway", "setup"]) == 0

    configured = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "AGORA_APP_ID=agora-app" in configured
    assert "AGORA_APP_CERTIFICATE=app-cert" in configured

    gateway_config = (root / ".synapse" / "config.yaml").read_text(encoding="utf-8")
    assert "enabled_gateways:" in gateway_config
    assert "- agora-convoai" in gateway_config
    assert "app_id: $AGORA_APP_ID" in gateway_config
    assert "credential_mode: managed" in gateway_config
    assert "vendor: minimax" in gateway_config


def test_gateway_setup_decline_disables_existing_gateway_config(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    write_template(root / ".env.example")
    configure_repo_paths(monkeypatch, root)
    monkeypatch.setattr(cli_main, "setup_can_prompt", lambda: True)
    (root / ".synapse").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / "config.yaml").write_text(
        "\n".join(
            [
                "version: 1",
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
    assert "enabled: false" in configured
    assert "enabled_gateways:" in configured


def test_gateway_listing_and_settings_do_not_require_fastapi(monkeypatch, tmp_path: Path):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    write_template(root / ".env.example")
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
    write_template(root / ".env.example")

    configure_repo_paths(monkeypatch, root)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

    assert cli_main.main(["setup", "--non-interactive"]) == 0

    configured = (root / ".synapse" / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-env" in configured
    assert "SYNAPSE_CODEX_EXECUTOR_ENABLED=false" in configured
    assert "# SYNAPSE_CODEX_COMMAND=codex" in configured


def test_setup_non_interactive_requires_openai(monkeypatch, tmp_path: Path, capsys):
    root = tmp_path
    (root / "src" / "synapse" / "ui").mkdir(parents=True)
    write_template(root / ".env.example")

    configure_repo_paths(monkeypatch, root)

    assert cli_main.main(["setup", "--non-interactive"]) == 1
    assert "OPENAI_API_KEY is required for non-interactive setup" in capsys.readouterr().err


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
