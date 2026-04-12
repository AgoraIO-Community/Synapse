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
    app_name: str = "Synapse v2"
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
        app_name=os.getenv("SYNAPSE_APP_NAME", "Synapse v2"),
        communication_backend=os.getenv("SYNAPSE_COMMUNICATION_BACKEND", "auto"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("SYNAPSE_OPENAI_MODEL", "gpt-4o-mini"),
        openai_timeout_seconds=float(os.getenv("SYNAPSE_OPENAI_TIMEOUT_SECONDS", "30")),
        openai_base_url=os.getenv("SYNAPSE_OPENAI_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or None,
        codex_executor_enabled=_get_bool("SYNAPSE_CODEX_EXECUTOR_ENABLED", False),
        codex_command=os.getenv("SYNAPSE_CODEX_COMMAND", "codex"),
        log_level=os.getenv("SYNAPSE_LOG_LEVEL", "INFO").upper(),
        log_format=os.getenv("SYNAPSE_LOG_FORMAT", "auto").lower(),
        log_color=os.getenv("SYNAPSE_LOG_COLOR", "auto").lower(),
        quiet_diagnostics_access_logs=_get_bool("SYNAPSE_QUIET_DIAGNOSTICS_ACCESS_LOGS", True),
        log_llm_details=_get_bool("SYNAPSE_LOG_LLM_DETAILS", False),
        diagnostic_max_events=int(os.getenv("SYNAPSE_DIAGNOSTIC_MAX_EVENTS", "500")),
        git_sha=os.getenv("SYNAPSE_GIT_SHA") or None,
    )
