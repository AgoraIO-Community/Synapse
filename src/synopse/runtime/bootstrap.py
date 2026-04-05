from __future__ import annotations

from synopse.communication.model import CommunicationDecision
from synopse.communication.models import OpenAICommunicationModel, ScriptedCommunicationModel
from synopse.infrastructure.llm import OpenAIProvider

from .container import RuntimeContainer
from .config import Settings, load_settings


def build_runtime_container(
    *,
    settings: Settings | None = None,
    provider: OpenAIProvider | None = None,
) -> RuntimeContainer:
    settings = settings or load_settings()
    if settings.communication_backend != "scripted" and settings.openai_api_key:
        model = OpenAICommunicationModel(provider or OpenAIProvider(settings))
        return RuntimeContainer(communication_model=model)

    default_model = ScriptedCommunicationModel(
        {
            "__default__": CommunicationDecision(
                conversational_act="request_clarification",
                reply_override="I need a more specific instruction for that.",
            )
        }
    )
    return RuntimeContainer(communication_model=default_model)
