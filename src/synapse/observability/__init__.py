from __future__ import annotations

from .schema import DiagnosticEvent, DiagnosticLevel
from .store import InMemoryDiagnosticStore


def __getattr__(name: str):
    if name in {"SessionObservability", "build_session_observability"}:
        from .bootstrap import SessionObservability, build_session_observability

        exports = {
            "SessionObservability": SessionObservability,
            "build_session_observability": build_session_observability,
        }
        return exports[name]
    raise AttributeError(name)


__all__ = [
    "DiagnosticEvent",
    "DiagnosticLevel",
    "InMemoryDiagnosticStore",
    "SessionObservability",
    "build_session_observability",
]
