from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from .context import CommunicationContext
from .types import ToolInvocationRecord

if TYPE_CHECKING:
    from .tools import ToolRegistry


TextDeltaCallback = Callable[[str], Awaitable[None] | None]


@dataclass(slots=True)
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommunicationModelResult:
    reply_text: str
    tool_invocations: list[ToolInvocationRecord] = field(default_factory=list)
    affected_task_ids: list[str] = field(default_factory=list)
    conversational_act: str | None = None


class CommunicationModel(Protocol):
    async def respond(
        self,
        *,
        user_text: str,
        context: CommunicationContext,
        tool_registry: "ToolRegistry",
        on_text_delta: TextDeltaCallback | None = None,
    ) -> CommunicationModelResult:
        ...
