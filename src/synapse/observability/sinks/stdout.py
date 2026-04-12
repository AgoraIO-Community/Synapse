from __future__ import annotations

import sys
from typing import TextIO

from .types import DiagnosticSink
from ..schema import DiagnosticEvent


class StdoutDiagnosticSink(DiagnosticSink):
    def __init__(self, *, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def emit(self, event: DiagnosticEvent) -> None:
        self._stream.write(event.model_dump_json() + "\n")
        self._stream.flush()
