from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_ENV_FILE = REPO_ROOT / ".env.local"


def load_local_env() -> None:
    load_dotenv(LOCAL_ENV_FILE, override=False)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_name: str = "Synopse v2"
    communication_backend: str = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_base_url: str | None = None
    codex_executor_enabled: bool = False
    codex_command: str = "codex"
    log_level: str = "INFO"
    log_format: str = "auto"
    log_color: str = "auto"
    quiet_diagnostics_access_logs: bool = True
    log_llm_details: bool = False
    diagnostic_max_events: int = 500
    git_sha: str | None = None


def load_settings() -> Settings:
    load_local_env()
    return Settings(
        app_name=os.getenv("SYNOPSE_APP_NAME", "Synopse v2"),
        communication_backend=os.getenv("SYNOPSE_COMMUNICATION_BACKEND", "auto"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("SYNOPSE_OPENAI_MODEL", "gpt-4o-mini"),
        openai_timeout_seconds=float(os.getenv("SYNOPSE_OPENAI_TIMEOUT_SECONDS", "30")),
        openai_base_url=os.getenv("SYNOPSE_OPENAI_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or None,
        codex_executor_enabled=_get_bool("SYNOPSE_CODEX_EXECUTOR_ENABLED", False),
        codex_command=os.getenv("SYNOPSE_CODEX_COMMAND", "codex"),
        log_level=os.getenv("SYNOPSE_LOG_LEVEL", "INFO").upper(),
        log_format=os.getenv("SYNOPSE_LOG_FORMAT", "auto").lower(),
        log_color=os.getenv("SYNOPSE_LOG_COLOR", "auto").lower(),
        quiet_diagnostics_access_logs=_get_bool("SYNOPSE_QUIET_DIAGNOSTICS_ACCESS_LOGS", True),
        log_llm_details=_get_bool("SYNOPSE_LOG_LLM_DETAILS", False),
        diagnostic_max_events=int(os.getenv("SYNOPSE_DIAGNOSTIC_MAX_EVENTS", "500")),
        git_sha=os.getenv("SYNOPSE_GIT_SHA") or None,
    )
