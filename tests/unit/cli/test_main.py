from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest

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


def test_setup_creates_env_file_and_installs(monkeypatch, tmp_path: Path):
    root = tmp_path
    frontend = root / "frontend"
    frontend.mkdir()
    (root / ".env.example").write_text("OPENAI_API_KEY=test\n", encoding="utf-8")
    venv_python = root / ".venv" / "bin" / "python"
    commands: list[tuple[list[str], Path]] = []

    def fake_run(cmd: list[str], cwd: Path, check: bool) -> FakeCompletedProcess:
        commands.append((cmd, cwd))
        if cmd[:3] == [sys.executable, "-m", "venv"]:
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("", encoding="utf-8")
        return FakeCompletedProcess()

    monkeypatch.setattr(cli_main, "ROOT", root)
    monkeypatch.setattr(cli_main, "FRONTEND", frontend)
    monkeypatch.setattr(cli_main, "VENV_DIR", root / ".venv")
    monkeypatch.setattr(cli_main, "ENV_EXAMPLE", root / ".env.example")
    monkeypatch.setattr(cli_main, "ENV_LOCAL", root / ".env.local")
    monkeypatch.setattr(cli_main, "preferred_frontend_tool", lambda: "npm")
    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)

    assert cli_main.main(["setup"]) == 0
    assert (root / ".env.local").read_text(encoding="utf-8") == "OPENAI_API_KEY=test\n"
    assert commands[0][0][:3] == [sys.executable, "-m", "venv"]
    assert commands[-1][0] == ["npm", "install"]


def test_backend_requires_setup(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cli_main, "VENV_DIR", tmp_path / ".venv")

    assert cli_main.main(["backend"]) == 1


def test_doctor_reads_openai_key_from_env_file(monkeypatch, tmp_path: Path, capsys):
    env_local = tmp_path / ".env.local"
    env_local.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(cli_main, "ROOT", tmp_path)
    monkeypatch.setattr(cli_main, "VENV_DIR", tmp_path / ".venv")
    monkeypatch.setattr(cli_main, "ENV_LOCAL", env_local)
    monkeypatch.setattr(cli_main, "report_port", lambda _port: True)
    monkeypatch.setattr(cli_main, "report_command", lambda _name, required=True: True)

    assert cli_main.main(["doctor"]) == 0
    assert "[ok] env: OPENAI_API_KEY" in capsys.readouterr().out


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
    processes = [FakeProcess(0), FakeProcess(None)]

    def fake_popen(cmd: list[str], cwd: Path):
        spawned.append((cmd, cwd))
        return processes[len(spawned) - 1]

    monkeypatch.setattr(cli_main, "ROOT", tmp_path)
    monkeypatch.setattr(cli_main, "FRONTEND", tmp_path / "frontend")
    monkeypatch.setattr(cli_main, "VENV_DIR", tmp_path / ".venv")
    monkeypatch.setattr(cli_main.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(cli_main.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main, "frontend_dev_command", lambda host, port: ["npm", "run", "dev", "--", "--host", host, "--port", str(port)])

    assert cli_main.main(["dev"]) == 0
    assert spawned[0][0][:4] == [str(venv_python), "-m", "uvicorn", "synapse.api.app:app"]
    assert spawned[1][0] == ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
