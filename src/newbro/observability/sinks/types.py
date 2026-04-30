from __future__ import annotations

from typing import Protocol

from ..schema import DiagnosticEvent


class DiagnosticSink(Protocol):
    def emit(self, event: DiagnosticEvent) -> None:
        ...
