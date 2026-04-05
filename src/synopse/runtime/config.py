from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_ENV_FILE = REPO_ROOT / ".env.local"


def load_local_env() -> None:
    load_dotenv(LOCAL_ENV_FILE, override=False)


@dataclass(slots=True)
class Settings:
    app_name: str = "Synopse v2"
    communication_backend: str = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_base_url: str | None = None


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
    )
