"""Runtime composition package scaffold."""

from importlib import import_module

from .config import Settings, load_settings


def build_runtime_container(*args, **kwargs):
    from .bootstrap import build_runtime_container as _build_runtime_container

    return _build_runtime_container(*args, **kwargs)


def __getattr__(name: str):
    if name == "RuntimeContainer":
        from .container import RuntimeContainer

        return RuntimeContainer
    if name == "SessionSnapshot":
        from .models import SessionSnapshot

        return SessionSnapshot
    if name == "bootstrap":
        return import_module(".bootstrap", __name__)
    raise AttributeError(name)


__all__ = ["RuntimeContainer", "SessionSnapshot", "Settings", "build_runtime_container", "load_settings"]
