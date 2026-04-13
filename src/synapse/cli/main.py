from __future__ import annotations

import argparse
from dataclasses import dataclass
import getpass
import os
from pathlib import Path
import re
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
ENV_LINE_RE = re.compile(r"^\s*(?P<comment>#\s*)?(?P<key>[A-Z0-9_]+)=(?P<value>.*)$")
TRUTHY_VALUES = {"1", "true", "yes", "on", "y"}
FALSY_VALUES = {"0", "false", "no", "off", "n"}
OPENAI_KEY = "OPENAI_API_KEY"
CODEX_ENABLED_KEY = "SYNAPSE_CODEX_EXECUTOR_ENABLED"
CODEX_COMMAND_KEY = "SYNAPSE_CODEX_COMMAND"
INTERACTIVE_SETUP_KEYS = {OPENAI_KEY, CODEX_ENABLED_KEY, CODEX_COMMAND_KEY}
GATEWAY_ENABLED_KEY = "SYNAPSE_GATEWAY_ENABLED"
GATEWAY_HOST_KEY = "SYNAPSE_GATEWAY_HOST"
GATEWAY_PORT_KEY = "SYNAPSE_GATEWAY_PORT"
GATEWAY_PUBLIC_BASE_URL_KEY = "SYNAPSE_GATEWAY_PUBLIC_BASE_URL"
GATEWAY_SYNAPSE_BASE_URL_KEY = "SYNAPSE_GATEWAY_SYNAPSE_BASE_URL"
GATEWAY_MODULES_KEY = "SYNAPSE_GATEWAY_MODULES"


@dataclass(slots=True)
class EnvTemplateLine:
    raw: str
    key: str | None = None
    value: str | None = None
    commented: bool = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="synapse", description="Synapse developer CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Interactively configure the root .env.local.")
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Resolve values from .env.local and process env without prompting.",
    )

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

    gateway_parser = subparsers.add_parser("gateway", help="Configure and run the gateway host.")
    gateway_subparsers = gateway_parser.add_subparsers(dest="gateway_command", required=True)
    gateway_subparsers.add_parser("setup", help="Interactively configure gateway modules.")
    gateway_run_parser = gateway_subparsers.add_parser("run", help="Run the headless gateway host.")
    gateway_run_parser.add_argument("--host")
    gateway_run_parser.add_argument("--port", type=int)
    gateway_run_parser.add_argument(
        "--reload",
        action="store_true",
        help="Run the gateway host with reload enabled.",
    )

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
            "gateway": cmd_gateway,
        }
        return handlers[args.command](args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def cmd_setup(_args: argparse.Namespace) -> int:
    args = _args
    if not ENV_EXAMPLE.exists():
        raise CliError(f"Missing env template: {ENV_EXAMPLE}")
    if not args.non_interactive and not setup_can_prompt():
        raise CliError("synapse setup requires a TTY. Use --non-interactive for automation.")

    template_lines = load_env_template(ENV_EXAMPLE)
    existing_values, existing_order = load_env_assignments(ENV_LOCAL)
    resolved_values = resolve_setup_values(
        template_lines=template_lines,
        existing_values=existing_values,
        environ=os.environ,
        interactive=not args.non_interactive,
    )
    gateway_values = resolve_gateway_setup_values(
        existing_values=existing_values,
        environ=os.environ,
        interactive=not args.non_interactive,
        force_prompt=False,
    )
    resolved_values.update(gateway_values)
    write_env_file(
        template_lines=template_lines,
        resolved_values=resolved_values,
        existing_values=existing_values,
        existing_order=existing_order,
        destination=ENV_LOCAL,
    )
    print(f"[write] configured {ENV_LOCAL.relative_to(ROOT)}")
    return 0


def cmd_dev(args: argparse.Namespace) -> int:
    venv_python = require_venv_python()
    commands = [
        ("backend", backend_command(venv_python, args.host, args.port, reload=True), ROOT),
        ("frontend", frontend_dev_command(args.host, args.frontend_port), FRONTEND),
    ]
    gateway_settings = load_gateway_settings_if_enabled()
    if gateway_settings is not None:
        commands.append(
            (
                "gateway",
                gateway_command(
                    venv_python,
                    gateway_settings.host,
                    gateway_settings.port,
                    reload=True,
                ),
                ROOT,
            )
        )

    print("\nSynapse dev is running")
    print(f"Frontend: http://localhost:{args.frontend_port}")
    print(f"Backend : http://localhost:{args.port}")
    if gateway_settings is not None:
        print(f"Gateway : {gateway_settings.public_base_url}")
    print("Press Ctrl+C to stop\n")
    return run_managed_processes(commands)


def cmd_backend(args: argparse.Namespace) -> int:
    venv_python = require_venv_python()
    return run_checked(backend_command(venv_python, args.host, args.port, reload=True), cwd=ROOT)


def cmd_start(args: argparse.Namespace) -> int:
    venv_python = require_venv_python()
    commands = [("backend", backend_command(venv_python, args.host, args.port, reload=False), ROOT)]
    gateway_settings = load_gateway_settings_if_enabled()
    if gateway_settings is not None:
        commands.append(
            (
                "gateway",
                gateway_command(
                    venv_python,
                    gateway_settings.host,
                    gateway_settings.port,
                    reload=False,
                ),
                ROOT,
            )
        )
    return run_managed_processes(commands)


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
        print("[missing] virtualenv: run ./install.sh")
        ok = False

    ok &= report_port(args.backend_port)
    ok &= report_port(args.frontend_port)

    if ENV_LOCAL.exists():
        print(f"[ok] env file: {ENV_LOCAL.relative_to(ROOT)}")
    else:
        print("[missing] env file: run ./synapse setup")
        ok = False

    if openai_api_key_present():
        print("[ok] env: OPENAI_API_KEY")
    else:
        print("[missing] env: OPENAI_API_KEY (run ./synapse setup)")
        ok = False

    ok &= report_gateway_status(args)

    return 0 if ok else 1


def cmd_gateway(args: argparse.Namespace) -> int:
    if args.gateway_command == "setup":
        return cmd_gateway_setup(args)
    if args.gateway_command == "run":
        return cmd_gateway_run(args)
    raise CliError(f"Unknown gateway command: {args.gateway_command}")


def cmd_gateway_setup(_args: argparse.Namespace) -> int:
    if not ENV_EXAMPLE.exists():
        raise CliError(f"Missing env template: {ENV_EXAMPLE}")
    if not setup_can_prompt():
        raise CliError("synapse gateway setup requires a TTY.")

    template_lines = load_env_template(ENV_EXAMPLE)
    existing_values, existing_order = load_env_assignments(ENV_LOCAL)
    resolved_values = resolve_gateway_setup_values(
        existing_values=existing_values,
        environ=os.environ,
        interactive=True,
        force_prompt=True,
    )
    write_env_file(
        template_lines=template_lines,
        resolved_values={**existing_values, **resolved_values},
        existing_values=existing_values,
        existing_order=existing_order,
        destination=ENV_LOCAL,
    )
    print(f"[write] configured {ENV_LOCAL.relative_to(ROOT)}")
    return 0


def cmd_gateway_run(args: argparse.Namespace) -> int:
    venv_python = require_venv_python()
    settings = load_gateway_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    return run_checked(gateway_command(venv_python, host, port, reload=args.reload), cwd=ROOT)


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


def gateway_command(venv_python: Path, host: str, port: int, *, reload: bool) -> list[str]:
    command = [
        str(venv_python),
        "-m",
        "uvicorn",
        "synapse.gateway_host.app:app",
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
    raise CliError("Repo virtualenv is not ready. Run ./install.sh first.")


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


def run_managed_processes(commands: list[tuple[str, list[str], Path]]) -> int:
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

    for name, cmd, cwd in commands:
        start_process(name, cmd, cwd)

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


def setup_can_prompt() -> bool:
    return sys.stdin.isatty()


def load_env_template(path: Path) -> list[EnvTemplateLine]:
    lines: list[EnvTemplateLine] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_LINE_RE.match(raw_line)
        if not match:
            lines.append(EnvTemplateLine(raw=raw_line))
            continue
        lines.append(
            EnvTemplateLine(
                raw=raw_line,
                key=match.group("key"),
                value=match.group("value"),
                commented=match.group("comment") is not None,
            )
        )
    return lines


def load_env_assignments(path: Path) -> tuple[dict[str, str], list[str]]:
    if not path.exists():
        return {}, []

    values: dict[str, str] = {}
    order: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_LINE_RE.match(raw_line)
        if not match or match.group("comment") is not None:
            continue
        key = match.group("key")
        if key not in values:
            order.append(key)
        values[key] = match.group("value")
    return values, order


def resolve_setup_values(
    *,
    template_lines: list[EnvTemplateLine],
    existing_values: dict[str, str],
    environ: os._Environ[str],
    interactive: bool,
) -> dict[str, str | None]:
    template_values = {line.key: line.value for line in template_lines if line.key is not None}
    resolved: dict[str, str | None] = {}

    for line in template_lines:
        if line.key is None or line.key in INTERACTIVE_SETUP_KEYS:
            continue
        current_value = pick_env_value(line.key, existing_values, environ)
        if current_value is None and not line.commented:
            current_value = line.value
        resolved[line.key] = normalize_optional_value(current_value)

    openai_default = normalize_required_value(
        pick_env_value(OPENAI_KEY, existing_values, environ),
        placeholder=template_values.get(OPENAI_KEY),
    )
    if interactive:
        resolved[OPENAI_KEY] = prompt_secret_value(OPENAI_KEY, default_value=openai_default)
    else:
        if openai_default is None:
            raise CliError(
                "OPENAI_API_KEY is required for non-interactive setup. Set it in .env.local or the shell environment."
            )
        resolved[OPENAI_KEY] = openai_default

    explicit_codex_enabled = pick_env_value(CODEX_ENABLED_KEY, existing_values, environ)
    codex_enabled = resolve_codex_enabled(explicit_codex_enabled, interactive=interactive)
    resolved[CODEX_ENABLED_KEY] = format_bool(codex_enabled)

    existing_codex_command = pick_env_value(CODEX_COMMAND_KEY, existing_values, environ)
    default_codex_command = existing_codex_command or template_values.get(CODEX_COMMAND_KEY) or "codex"
    if interactive and codex_enabled and not _codex_command_available(default_codex_command):
        codex_command = prompt_text_value("Codex command", default_value=default_codex_command, required=True)
        if not _codex_command_available(codex_command):
            print(f"[warn] command '{codex_command}' is not currently available on PATH")
        resolved[CODEX_COMMAND_KEY] = codex_command
    elif codex_enabled:
        resolved[CODEX_COMMAND_KEY] = default_codex_command
    elif existing_codex_command:
        resolved[CODEX_COMMAND_KEY] = existing_codex_command
    else:
        resolved[CODEX_COMMAND_KEY] = None

    return resolved


def resolve_gateway_setup_values(
    *,
    existing_values: dict[str, str],
    environ: os._Environ[str],
    interactive: bool,
    force_prompt: bool,
) -> dict[str, str | None]:
    if not interactive:
        return {}

    existing_enabled = pick_env_value(GATEWAY_ENABLED_KEY, existing_values, environ)
    default_enabled = parse_bool_value(existing_enabled) if existing_enabled is not None else False
    should_configure = prompt_bool_value("Configure gateway host", default=bool(default_enabled or force_prompt))
    if not should_configure:
        if not force_prompt:
            return {}
        return {
            GATEWAY_ENABLED_KEY: "false",
            GATEWAY_MODULES_KEY: None,
        }

    modules = prompt_gateway_module_selection()
    host = prompt_text_value(
        "Gateway host",
        default_value=pick_env_value(GATEWAY_HOST_KEY, existing_values, environ) or "0.0.0.0",
        required=True,
    )
    port = prompt_text_value(
        "Gateway port",
        default_value=pick_env_value(GATEWAY_PORT_KEY, existing_values, environ) or "8010",
        required=True,
    )
    public_base_url = prompt_text_value(
        "Gateway public base URL",
        default_value=pick_env_value(GATEWAY_PUBLIC_BASE_URL_KEY, existing_values, environ)
        or f"http://127.0.0.1:{port}",
        required=True,
    )
    synapse_base_url = prompt_text_value(
        "Synapse API base URL for gateway callbacks",
        default_value=pick_env_value(GATEWAY_SYNAPSE_BASE_URL_KEY, existing_values, environ)
        or "http://127.0.0.1:8000",
        required=True,
    )

    resolved: dict[str, str | None] = {
        GATEWAY_ENABLED_KEY: "true",
        GATEWAY_HOST_KEY: host,
        GATEWAY_PORT_KEY: port,
        GATEWAY_PUBLIC_BASE_URL_KEY: public_base_url,
        GATEWAY_SYNAPSE_BASE_URL_KEY: synapse_base_url,
        GATEWAY_MODULES_KEY: ",".join(modules),
    }
    for module in modules:
        if module == "agora-convoai":
            resolved.update(resolve_agora_gateway_setup_values(existing_values, environ))
    return resolved


def resolve_agora_gateway_setup_values(
    existing_values: dict[str, str],
    environ: os._Environ[str],
) -> dict[str, str | None]:
    return {
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_ID": prompt_text_value(
            "Agora App ID",
            default_value=pick_env_value("SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_ID", existing_values, environ)
            or pick_env_value("AGORA_APP_ID", existing_values, environ),
            required=True,
        ),
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_CERTIFICATE": prompt_secret_value(
            "Agora App Certificate",
            default_value=pick_env_value(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_CERTIFICATE",
                existing_values,
                environ,
            )
            or pick_env_value("AGORA_APP_CERTIFICATE", existing_values, environ),
        ),
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_AREA": prompt_text_value(
            "Agora ConvoAI area",
            default_value=pick_env_value("SYNAPSE_GATEWAY_AGORA_CONVOAI_AREA", existing_values, environ)
            or pick_env_value("AGORA_CONVOAI_AREA", existing_values, environ)
            or "CN",
            required=True,
        ),
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_API_KEY": prompt_secret_value(
            "Deepgram API Key",
            default_value=pick_env_value(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_API_KEY",
                existing_values,
                environ,
            )
            or pick_env_value("DEEPGRAM_API_KEY", existing_values, environ),
        ),
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_LANGUAGE": prompt_text_value(
            "Deepgram language",
            default_value=pick_env_value(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_LANGUAGE",
                existing_values,
                environ,
            )
            or pick_env_value("AGORA_DEEPGRAM_LANGUAGE", existing_values, environ)
            or "en-US",
            required=True,
        ),
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_API_KEY": prompt_secret_value(
            "ElevenLabs API Key",
            default_value=pick_env_value(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_API_KEY",
                existing_values,
                environ,
            )
            or pick_env_value("ELEVENLABS_API_KEY", existing_values, environ),
        ),
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_VOICE_ID": prompt_text_value(
            "ElevenLabs Voice ID",
            default_value=pick_env_value(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_VOICE_ID",
                existing_values,
                environ,
            )
            or pick_env_value("ELEVENLABS_VOICE_ID", existing_values, environ),
            required=True,
        ),
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_MODEL": prompt_text_value(
            "Gateway model label",
            default_value=pick_env_value(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_MODEL",
                existing_values,
                environ,
            )
            or pick_env_value("AGORA_BRIDGE_MODEL", existing_values, environ)
            or "synapse-agora-bridge",
            required=True,
        ),
    }


def write_env_file(
    *,
    template_lines: list[EnvTemplateLine],
    resolved_values: dict[str, str | None],
    existing_values: dict[str, str],
    existing_order: list[str],
    destination: Path,
) -> None:
    known_keys = [line.key for line in template_lines if line.key is not None]
    rendered_lines: list[str] = []

    for line in template_lines:
        if line.key is None:
            rendered_lines.append(line.raw)
            continue

        resolved_value = resolved_values.get(line.key)
        if resolved_value is None or resolved_value == "":
            if line.commented:
                rendered_lines.append(line.raw)
            elif line.value is not None:
                rendered_lines.append(f"{line.key}={line.value}")
            else:
                rendered_lines.append(f"{line.key}=")
            continue

        rendered_lines.append(f"{line.key}={resolved_value}")

    unknown_keys = [key for key in existing_order if key not in known_keys]
    additional_resolved_keys = [
        key
        for key, value in resolved_values.items()
        if key not in known_keys and key not in unknown_keys and value not in (None, "")
    ]
    if unknown_keys:
        if rendered_lines and rendered_lines[-1] != "":
            rendered_lines.append("")
        for key in unknown_keys:
            rendered_lines.append(f"{key}={existing_values[key]}")
    if additional_resolved_keys:
        if rendered_lines and rendered_lines[-1] != "":
            rendered_lines.append("")
        for key in additional_resolved_keys:
            rendered_lines.append(f"{key}={resolved_values[key]}")

    destination.write_text("\n".join(rendered_lines) + "\n", encoding="utf-8")


def pick_env_value(name: str, existing_values: dict[str, str], environ: os._Environ[str]) -> str | None:
    if name in existing_values:
        return existing_values[name]
    return environ.get(name)


def normalize_optional_value(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


def normalize_required_value(value: str | None, *, placeholder: str | None) -> str | None:
    if value is None or value == "" or value == placeholder:
        return None
    return value


def _codex_command_available(command: str) -> bool:
    return shutil.which(command) is not None


def resolve_codex_enabled(explicit_value: str | None, *, interactive: bool) -> bool:
    if explicit_value is not None:
        parsed = parse_bool_value(explicit_value)
        if parsed is None:
            raise CliError(
                f"{CODEX_ENABLED_KEY} must be one of true/false/yes/no/1/0, got '{explicit_value}'."
            )
        explicit_default = parsed
    else:
        explicit_default = None

    if not interactive:
        return explicit_default if explicit_default is not None else False

    default_value = explicit_default if explicit_default is not None else _codex_command_available("codex")
    return prompt_bool_value("Enable Codex executor", default=default_value)


def parse_bool_value(raw_value: str) -> bool | None:
    normalized = raw_value.strip().lower()
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False
    return None


def format_bool(value: bool) -> str:
    return "true" if value else "false"


def prompt_secret_value(name: str, *, default_value: str | None) -> str:
    while True:
        suffix = " [configured]" if default_value else ""
        entered = getpass.getpass(f"{name}{suffix}: ")
        if entered:
            return entered
        if default_value:
            return default_value
        print(f"{name} is required.")


def prompt_bool_value(label: str, *, default: bool) -> bool:
    prompt = "Y/n" if default else "y/N"
    while True:
        entered = input(f"{label} [{prompt}]: ").strip()
        if not entered:
            return default
        parsed = parse_bool_value(entered)
        if parsed is not None:
            return parsed
        print("Please answer yes or no.")


def prompt_gateway_module_selection() -> list[str]:
    modules = list_available_gateway_modules()
    if not modules:
        raise CliError("No gateway modules are currently registered.")

    print("Available gateway modules:")
    for index, module in enumerate(modules, start=1):
        print(f"  {index}. {module}")

    while True:
        entered = input("Select gateway modules [1]: ").strip()
        if not entered:
            return [modules[0]]
        selected: list[str] = []
        try:
            for part in entered.split(","):
                index = int(part.strip())
                selected.append(modules[index - 1])
        except (ValueError, IndexError):
            print("Enter one or more numeric choices separated by commas.")
            continue
        deduped: list[str] = []
        for module in selected:
            if module not in deduped:
                deduped.append(module)
        return deduped


def prompt_text_value(label: str, *, default_value: str | None, required: bool = False) -> str:
    while True:
        suffix = f" [{default_value}]" if default_value else ""
        entered = input(f"{label}{suffix}: ").strip()
        if entered:
            return entered
        if default_value:
            return default_value
        if not required:
            return ""
        print(f"{label} is required.")


def list_available_gateway_modules() -> list[str]:
    from synapse.gateway_host.catalog import list_gateway_module_specs

    return [spec.slug for spec in list_gateway_module_specs()]


def load_gateway_settings():
    import importlib
    gateway_config_module = importlib.import_module("synapse.gateway_host.config")
    return gateway_config_module.load_gateway_host_settings(env_file=ENV_LOCAL)


def load_gateway_settings_if_enabled():
    settings = load_gateway_settings()
    if not settings.enabled or not settings.enabled_modules:
        return None
    return settings


def report_gateway_status(args: argparse.Namespace) -> bool:
    settings = load_gateway_settings()
    if not settings.enabled:
        print("[ok] gateway: disabled")
        return True

    ok = True
    modules = ", ".join(settings.enabled_modules) or "(none)"
    print(f"[ok] gateway: enabled -> {modules}")
    print(f"[ok] gateway public URL: {settings.public_base_url}")
    ok &= report_port(settings.port)

    for module in settings.enabled_modules:
        if module == "agora-convoai":
            ok &= report_required_env_keys(
                [
                    "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_ID",
                    "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_CERTIFICATE",
                    "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_API_KEY",
                    "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_API_KEY",
                    "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_VOICE_ID",
                ]
            )
    return ok


def report_required_env_keys(keys: list[str]) -> bool:
    ok = True
    existing_values, _ = load_env_assignments(ENV_LOCAL)
    for key in keys:
        value = pick_env_value(key, existing_values, os.environ)
        if value:
            print(f"[ok] env: {key}")
        else:
            print(f"[missing] env: {key} (run ./synapse gateway setup)")
            ok = False
    return ok


class CliError(Exception):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
