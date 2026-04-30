from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module


@dataclass(frozen=True, slots=True)
class ConnectorModuleSpec:
    slug: str
    label: str
    description: str
    module_path: str
    class_name: str

    def load_module_class(self):
        module = import_module(self.module_path)
        return getattr(module, self.class_name)


def list_connector_module_specs() -> list[ConnectorModuleSpec]:
    return [
        ConnectorModuleSpec(
            slug="agora-convoai",
            label="Agora ConvoAI",
            description="Agora Conversational AI headless connector module.",
            module_path="newbro.connectors.voice.agora_convoai.module",
            class_name="AgoraConvoAIConnectorModule",
        )
    ]
