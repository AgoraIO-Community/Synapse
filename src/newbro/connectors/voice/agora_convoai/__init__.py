from .settings import AgoraConvoAIConnectorSettings, load_agora_connector_settings

__all__ = [
    "AgoraConvoAIConnectorModule",
    "AgoraConvoAIConnectorSettings",
    "create_headless_app",
    "load_agora_connector_settings",
]


def __getattr__(name: str):
    if name == "AgoraConvoAIConnectorModule":
        from .module import AgoraConvoAIConnectorModule

        return AgoraConvoAIConnectorModule
    if name == "create_headless_app":
        from .app import create_headless_app

        return create_headless_app
    raise AttributeError(name)
