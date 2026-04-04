from pathlib import Path
from dataclasses import dataclass
import os

from dotenv import load_dotenv


LOCAL_ENV_FILE = Path(__file__).resolve().parents[2] / ".env.local"
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    load_dotenv(LOCAL_ENV_FILE, override=False)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_name: str = "Synopse"
    default_executor_id: str | None = None
    mock_executor_tick_seconds: float = 0.02
    codex_executor_enabled: bool = False
    codex_executor_id: str = "codex_executor"
    codex_cli_path: str = "codex"
    codex_workdir: str = str(REPO_ROOT)
    codex_model: str | None = None
    codex_timeout_seconds: float = 180.0
    codex_sandbox: str = "workspace-write"
    codex_approval_policy: str = "on-request"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_base_url: str | None = None


def load_settings() -> Settings:
    load_local_env()
    configured_default_executor = os.getenv("SYNOPSE_DEFAULT_EXECUTOR_ID")
    return Settings(
        app_name=os.getenv("SYNOPSE_APP_NAME", "Synopse"),
        default_executor_id=configured_default_executor or None,
        mock_executor_tick_seconds=float(
            os.getenv("SYNOPSE_MOCK_EXECUTOR_TICK_SECONDS", "0.02")
        ),
        codex_executor_enabled=_env_flag("SYNOPSE_CODEX_EXECUTOR_ENABLED", False),
        codex_executor_id=os.getenv("SYNOPSE_CODEX_EXECUTOR_ID", "codex_executor"),
        codex_cli_path=os.getenv("SYNOPSE_CODEX_CLI_PATH", "codex"),
        codex_workdir=os.getenv("SYNOPSE_CODEX_WORKDIR", str(REPO_ROOT)),
        codex_model=os.getenv("SYNOPSE_CODEX_MODEL") or None,
        codex_timeout_seconds=float(
            os.getenv("SYNOPSE_CODEX_TIMEOUT_SECONDS", "180")
        ),
        codex_sandbox=os.getenv("SYNOPSE_CODEX_SANDBOX", "workspace-write"),
        codex_approval_policy=os.getenv(
            "SYNOPSE_CODEX_APPROVAL_POLICY", "on-request"
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("SYNOPSE_OPENAI_MODEL", "gpt-4o-mini"),
        openai_timeout_seconds=float(
            os.getenv("SYNOPSE_OPENAI_TIMEOUT_SECONDS", "30")
        ),
        openai_base_url=os.getenv("SYNOPSE_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
    )
