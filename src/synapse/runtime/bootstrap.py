from __future__ import annotations

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
