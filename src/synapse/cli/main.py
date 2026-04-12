from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend"
VENV_DIR = ROOT / ".venv"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_LOCAL = ROOT / ".env.local"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="synapse", description="Synapse developer CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup", help="Create the repo venv, install dependencies, and scaffold .env.local.")

    dev_parser = subparsers.add_parser("dev", help="Run backend and frontend together.")
    _add_host_port(dev_parser, backend_port=8000, frontend_port=5173, include_frontend_port=True)

    backend_parser = subparsers.add_parser("backend", help="Run the FastAPI backend with reload.")
    _add_host_port(backend_parser, backend_port=8000)

    frontend_parser = subparsers.add_parser("frontend", help="Run the frontend dev server.")
    frontend_parser.add_argument("--host", default="0.0.0.0")
    frontend_parser.add_argument("--port", type=int, default=5173)

    doctor_parser = subparsers.add_parser("doctor", help="Check local development prerequisites.")
    doctor_parser.add_argument("--backend-port", type=int, default=8000)
    doctor_parser.add_argument("--frontend-port", type=int, default=5173)

    start_parser = subparsers.add_parser("start", help="Run the FastAPI backend without reload.")
    _add_host_port(start_parser, backend_port=8000)

    return parser


def _add_host_port(parser: argparse.ArgumentParser, backend_port: int, frontend_port: int | None = None, include_frontend_port: bool = False) -> None:
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=backend_port)
    if include_frontend_port:
        parser.add_argument("--frontend-port", type=int, default=frontend_port or 5173)


def main(argv: list[str] | None = None) -> int:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)

        handlers = {
            "setup": cmd_setup,
            "dev": cmd_dev,
            "backend": cmd_backend,
            "frontend": cmd_frontend,
            "doctor": cmd_doctor,
            "start": cmd_start,
        }
        return handlers[args.command](args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def cmd_setup(_args: argparse.Namespace) -> int:
    if not VENV_DIR.exists():
        print(f"[create] virtual environment at {VENV_DIR}")
        run_checked([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=ROOT)

    venv_python = require_venv_python(allow_missing=False)
    run_checked([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=ROOT)
    run_checked([str(venv_python), "-m", "pip", "install", "-e", ".[dev]"], cwd=ROOT)

    install_cmd = frontend_install_command()
    run_checked(install_cmd, cwd=FRONTEND)

    if ENV_EXAMPLE.exists() and not ENV_LOCAL.exists():
        shutil.copyfile(ENV_EXAMPLE, ENV_LOCAL)
        print(f"[write] created {ENV_LOCAL.relative_to(ROOT)} from {ENV_EXAMPLE.relative_to(ROOT)}")

    return 0


def cmd_dev(args: argparse.Namespace) -> int:
    venv_python = require_venv_python()
    frontend_cmd = frontend_dev_command(args.host, args.frontend_port)
    processes: list[tuple[str, subprocess.Popen[str]]] = []

    def start_process(name: str, cmd: list[str], cwd: Path) -> subprocess.Popen[str]:
        print(f"[start] {name}: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, cwd=cwd)
        processes.append((name, process))
        return process

    def stop_all() -> None:
        for name, process in reversed(processes):
            if process.poll() is None:
                print(f"[stop] {name}")
                process.terminate()
        deadline = time.time() + 5
        for _, process in processes:
            while process.poll() is None and time.time() < deadline:
                time.sleep(0.1)
        for name, process in processes:
            if process.poll() is None:
                print(f"[kill] {name}")
                process.kill()

    def handle_signal(_signum: int, _frame) -> None:
        stop_all()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    start_process("backend", backend_command(venv_python, args.host, args.port, reload=True), ROOT)
    start_process("frontend", frontend_cmd, FRONTEND)

    print("\nSynapse dev is running")
    print(f"Frontend: http://localhost:{args.frontend_port}")
    print(f"Backend : http://localhost:{args.port}")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            for name, process in processes:
                code = process.poll()
                if code is not None:
                    print(f"[exit] {name} exited with code {code}")
                    stop_all()
                    return code
            time.sleep(1)
    finally:
        stop_all()


def cmd_backend(args: argparse.Namespace) -> int:
    venv_python = require_venv_python()
    return run_checked(backend_command(venv_python, args.host, args.port, reload=True), cwd=ROOT)


def cmd_start(args: argparse.Namespace) -> int:
    venv_python = require_venv_python()
    return run_checked(backend_command(venv_python, args.host, args.port, reload=False), cwd=ROOT)


def cmd_frontend(args: argparse.Namespace) -> int:
    require_venv_python()
    return run_checked(frontend_dev_command(args.host, args.port), cwd=FRONTEND)


def cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    ok &= report_path("python", sys.executable)
    frontend_ok = report_command("bun") or report_command("npm")
    ok &= frontend_ok
    report_command("docker", required=False)

    venv_python = venv_python_path()
    if venv_python.exists():
        print(f"[ok] virtualenv: {VENV_DIR.relative_to(ROOT)}")
        print(f"[ok] venv python: {venv_python}")
    else:
        print(f"[missing] virtualenv: run ./synapse setup")
        ok = False

    ok &= report_port(args.backend_port)
    ok &= report_port(args.frontend_port)

    if ENV_LOCAL.exists():
        print(f"[ok] env file: {ENV_LOCAL.relative_to(ROOT)}")
    else:
        print(f"[missing] env file: create {ENV_LOCAL.relative_to(ROOT)}")
        ok = False

    if openai_api_key_present():
        print("[ok] env: OPENAI_API_KEY")
    else:
        print("[missing] env: OPENAI_API_KEY")
        ok = False

    return 0 if ok else 1


def backend_command(venv_python: Path, host: str, port: int, *, reload: bool) -> list[str]:
    command = [
        str(venv_python),
        "-m",
        "uvicorn",
        "synapse.api.app:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    return command


def frontend_install_command() -> list[str]:
    frontend_tool = preferred_frontend_tool()
    if frontend_tool == "bun":
        return ["bun", "install"]
    return ["npm", "install"]


def frontend_dev_command(host: str, port: int) -> list[str]:
    frontend_tool = preferred_frontend_tool()
    if frontend_tool == "bun":
        return ["bun", "run", "dev", "--", "--host", host, "--port", str(port)]
    return ["npm", "run", "dev", "--", "--host", host, "--port", str(port)]


def preferred_frontend_tool() -> str:
    if shutil.which("bun"):
        return "bun"
    if shutil.which("npm"):
        return "npm"
    raise CliError("Missing frontend package manager: install Bun or npm.")


def require_venv_python(*, allow_missing: bool = False) -> Path:
    venv_python = venv_python_path()
    if venv_python.exists():
        return venv_python
    if allow_missing:
        return venv_python
    raise CliError("Repo virtualenv is not ready. Run ./synapse setup first.")


def venv_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_checked(cmd: list[str], cwd: Path) -> int:
    print(f"[run] {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed.returncode


def report_command(name: str, *, required: bool = True) -> bool:
    path = shutil.which(name)
    if path:
        print(f"[ok] command: {name} -> {path}")
        return True
    status = "missing" if required else "warn"
    print(f"[{status}] command: {name}")
    return not required


def report_path(label: str, value: str) -> bool:
    print(f"[ok] {label}: {value}")
    return True


def report_port(port: int) -> bool:
    try:
        sock = socket.socket()
    except PermissionError:
        print(f"[warn] port {port} could not be checked in this environment")
        return True

    try:
        sock.bind(("127.0.0.1", port))
        print(f"[ok] port {port} is free")
        return True
    except PermissionError:
        print(f"[warn] port {port} could not be checked in this environment")
        return True
    except OSError:
        print(f"[busy] port {port} is already in use")
        return False
    finally:
        sock.close()


def openai_api_key_present() -> bool:
    if os.getenv("OPENAI_API_KEY"):
        return True
    if not ENV_LOCAL.exists():
        return False
    for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == "OPENAI_API_KEY" and value.strip():
            return True
    return False


class CliError(Exception):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
