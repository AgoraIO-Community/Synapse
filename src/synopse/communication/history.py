from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(slots=True)
class ConversationEntry:
    role: str
    text: str
    message_id: str = field(default_factory=lambda: f"msg-{uuid4().hex[:8]}")


class InMemoryConversationHistory:
    def __init__(self) -> None:
        self._entries: dict[str, list[ConversationEntry]] = {}

    def append_user(self, conversation_id: str, text: str) -> ConversationEntry:
        entry = ConversationEntry(role="user", text=text)
        self._entries.setdefault(conversation_id, []).append(entry)
        return entry

    def append_assistant(self, conversation_id: str, text: str) -> ConversationEntry:
        entry = ConversationEntry(role="assistant", text=text)
        self._entries.setdefault(conversation_id, []).append(entry)
        return entry

    def get_recent(self, conversation_id: str, *, limit: int = 10) -> list[ConversationEntry]:
        return list(self._entries.get(conversation_id, [])[-limit:])
