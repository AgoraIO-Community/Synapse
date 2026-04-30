from __future__ import annotations

from importlib import import_module


__all__ = [
    "ApiDiagnosticEmitter",
    "BlackboardDiagnosticEmitter",
    "CommunicationDiagnosticEmitter",
    "ExecutionDiagnosticEmitter",
    "NotificationDiagnosticEmitter",
]


_MODULE_BY_NAME = {
    "ApiDiagnosticEmitter": ".api",
    "BlackboardDiagnosticEmitter": ".blackboard",
    "CommunicationDiagnosticEmitter": ".communication",
    "ExecutionDiagnosticEmitter": ".execution",
    "NotificationDiagnosticEmitter": ".notification",
}


def __getattr__(name: str):
    module_name = _MODULE_BY_NAME.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    return getattr(module, name)
