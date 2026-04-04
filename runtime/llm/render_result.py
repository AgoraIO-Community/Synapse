from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LLMResponseDetails:
    output_text: str
    duration_ms: int
    streamed: bool
    ttfb_ms: int | None = None

    def to_trace_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "output_text": self.output_text,
            "duration_ms": self.duration_ms,
            "streamed": self.streamed,
        }
        if self.ttfb_ms is not None:
            payload["ttfb_ms"] = self.ttfb_ms
        return payload


@dataclass(slots=True)
class LLMResponseStreamEvent:
    delta: str
    is_final: bool = False
    metadata: LLMResponseDetails | None = None
