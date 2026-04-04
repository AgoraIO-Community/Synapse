from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    app_name: str = "Synopse"
    default_executor_id: str = "mock_executor"
    use_stub_llm: bool = True
    mock_executor_tick_seconds: float = 0.02


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("SYNOPSE_APP_NAME", "Synopse"),
        default_executor_id=os.getenv("SYNOPSE_DEFAULT_EXECUTOR_ID", "mock_executor"),
        use_stub_llm=os.getenv("SYNOPSE_USE_STUB_LLM", "true").lower() != "false",
        mock_executor_tick_seconds=float(
            os.getenv("SYNOPSE_MOCK_EXECUTOR_TICK_SECONDS", "0.02")
        ),
    )
