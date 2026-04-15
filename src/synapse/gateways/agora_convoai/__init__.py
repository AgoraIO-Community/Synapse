from .settings import AgoraConvoAIGatewaySettings, load_agora_gateway_settings

__all__ = [
    "AgoraConvoAIGatewayModule",
    "AgoraConvoAIGatewaySettings",
    "create_headless_app",
    "load_agora_gateway_settings",
]


def __getattr__(name: str):
    if name == "AgoraConvoAIGatewayModule":
        from .module import AgoraConvoAIGatewayModule

        return AgoraConvoAIGatewayModule
    if name == "create_headless_app":
        from .app import create_headless_app

        return create_headless_app
    raise AttributeError(name)
