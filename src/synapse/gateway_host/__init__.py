__all__ = ["GatewayHostSettings", "app", "create_app", "load_gateway_host_settings"]


def __getattr__(name: str):
    if name in {"GatewayHostSettings", "load_gateway_host_settings"}:
        from .config import GatewayHostSettings, load_gateway_host_settings

        if name == "GatewayHostSettings":
            return GatewayHostSettings
        return load_gateway_host_settings
    if name in {"app", "create_app"}:
        from .app import app, create_app

        if name == "app":
            return app
        return create_app
    raise AttributeError(name)
