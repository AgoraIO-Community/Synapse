from __future__ import annotations

import shlex
import shutil

from synopse.communication.models import OpenAICommunicationModel, ScriptedCommunicationModel
from synopse.communication.models.scripted import ScriptedPlan
from synopse.infrastructure.llm import OpenAIProvider

from .config import Settings, load_settings
from .container import RuntimeContainer


def build_runtime_container(
    *,
    settings: Settings | None = None,
    provider: OpenAIProvider | None = None,
) -> RuntimeContainer:
    settings = settings or load_settings()
    if settings.codex_executor_enabled and not _command_available(settings.codex_command):
        raise RuntimeError(
            f"Codex executor is enabled but command '{settings.codex_command}' is not available. "
            "Install Codex CLI and make sure `codex` is available on PATH."
        )
    if settings.acpx_executor_enabled and not _command_available(settings.acpx_command):
        raise RuntimeError(
            f"ACPX executor is enabled but command '{settings.acpx_command}' is not available. "
            "Install it with `npm install -g acpx@latest`, or set "
            "`SYNOPSE_ACPX_COMMAND` to the correct executable path."
        )

    if settings.communication_backend != "scripted" and settings.openai_api_key:
        model = OpenAICommunicationModel(provider or OpenAIProvider(settings))
        return RuntimeContainer(communication_model=model, settings=settings)

    default_model = ScriptedCommunicationModel(
        {
            "__default__": ScriptedPlan(
                conversational_act="request_clarification",
                reply_override="I need a more specific instruction for that.",
            )
        }
    )
    return RuntimeContainer(communication_model=default_model, settings=settings)


def _command_available(command: str) -> bool:
    parts = shlex.split(command)
    if not parts:
        return False
    return shutil.which(parts[0]) is not None
