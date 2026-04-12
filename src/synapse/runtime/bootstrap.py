from __future__ import annotations

import shutil

from synapse.communication.models import OpenAICommunicationModel, ScriptedCommunicationModel
from synapse.communication.models.scripted import ScriptedPlan
from synapse.infrastructure.llm import OpenAIProvider

from .config import Settings, load_settings
from .container import RuntimeContainer


def build_runtime_container(
    *,
    settings: Settings | None = None,
    provider: OpenAIProvider | None = None,
) -> RuntimeContainer:
    settings = settings or load_settings()
    if settings.codex_executor_enabled and not _codex_command_available(settings.codex_command):
        raise RuntimeError(
            f"Codex executor is enabled but command '{settings.codex_command}' is not available."
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


def _codex_command_available(command: str) -> bool:
    return shutil.which(command) is not None
