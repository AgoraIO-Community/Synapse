from pathlib import Path
from dataclasses import dataclass
import os

from dotenv import load_dotenv


LOCAL_ENV_FILE = Path(__file__).resolve().parents[2] / ".env.local"


def load_local_env() -> None:
    load_dotenv(LOCAL_ENV_FILE, override=False)


@dataclass(slots=True)
class Settings:
    app_name: str = "Synopse"
    default_executor_id: str = "mock_executor"
    mock_executor_tick_seconds: float = 0.02
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_base_url: str | None = None


def load_settings() -> Settings:
    load_local_env()
    return Settings(
        app_name=os.getenv("SYNOPSE_APP_NAME", "Synopse"),
        default_executor_id=os.getenv("SYNOPSE_DEFAULT_EXECUTOR_ID", "mock_executor"),
        mock_executor_tick_seconds=float(
            os.getenv("SYNOPSE_MOCK_EXECUTOR_TICK_SECONDS", "0.02")
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("SYNOPSE_OPENAI_MODEL", "gpt-4o-mini"),
        openai_timeout_seconds=float(
            os.getenv("SYNOPSE_OPENAI_TIMEOUT_SECONDS", "30")
        ),
        openai_base_url=os.getenv("SYNOPSE_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
    )
