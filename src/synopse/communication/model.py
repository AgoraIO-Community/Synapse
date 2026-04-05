from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .context import CommunicationContext


@dataclass(slots=True)
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommunicationDecision:
    conversational_act: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    reply_override: str | None = None


class CommunicationModel(Protocol):
    async def decide(
        self,
        *,
        user_text: str,
        context: CommunicationContext,
    ) -> CommunicationDecision:
        ...
