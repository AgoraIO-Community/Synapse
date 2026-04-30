__all__ = ["ConnectorHostSettings", "app", "create_app", "load_connector_host_settings"]


def __getattr__(name: str):
    if name in {"ConnectorHostSettings", "load_connector_host_settings"}:
        from .config import ConnectorHostSettings, load_connector_host_settings

        if name == "ConnectorHostSettings":
            return ConnectorHostSettings
        return load_connector_host_settings
    if name in {"app", "create_app"}:
        from .app import app, create_app

        if name == "app":
            return app
        return create_app
    raise AttributeError(name)
