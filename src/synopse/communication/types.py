from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolInvocationRecord:
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None


@dataclass(slots=True)
class CommunicationTurnResult:
    message_id: str
    reply_text: str
    conversational_act: str
    tool_invocations: list[ToolInvocationRecord] = field(default_factory=list)
    affected_task_ids: list[str] = field(default_factory=list)
    notification_key_task_id: str | None = None
    notification_relevant_task_ids: list[str] = field(default_factory=list)
