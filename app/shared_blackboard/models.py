from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.protocols.conversation import ConversationAction
from app.protocols.stream import StreamEvent
from app.protocols.tasks import Task


@dataclass(slots=True)
class SessionState:
    session_id: str
    conversation_state: dict = field(default_factory=dict)
    task_registry: dict[str, Task] = field(default_factory=dict)
    strategy_state: dict = field(default_factory=dict)
    pending_clarifications: list[ConversationAction] = field(default_factory=list)
    event_log: list[StreamEvent] = field(default_factory=list)
    last_sequence: int = 0
    subscribers: list[asyncio.Queue] = field(default_factory=list)
