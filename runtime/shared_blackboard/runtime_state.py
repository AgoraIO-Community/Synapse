from __future__ import annotations

import asyncio
from collections.abc import Callable

from runtime.infrastructure.ids import new_id
from runtime.infrastructure.time import utc_now
from runtime.protocols.conversation import ConversationAction
from runtime.protocols.execution import ExecutorCapability
from runtime.protocols.stream import SessionSnapshot, StreamCategory, StreamEvent
from runtime.shared_blackboard.blackboard_state import BlackboardSessionState
from runtime.shared_blackboard.mutations import MESSAGE_HISTORY_KEY, get_message_history


class RuntimeStateStore:
    def __init__(
        self,
        executor_capabilities_provider: Callable[[], list[ExecutorCapability]] | None = None,
    ) -> None:
        self._sessions: dict[str, BlackboardSessionState] = {}
        self._executor_capabilities_provider = (
            executor_capabilities_provider or (lambda: [])
        )

    def create_session(self) -> BlackboardSessionState:
        session = BlackboardSessionState(session_id=new_id("session"))
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> BlackboardSessionState:
        if session_id not in self._sessions:
            raise KeyError(f"Unknown session: {session_id}")
        return self._sessions[session_id]

    def snapshot(self, session_id: str) -> SessionSnapshot:
        session = self.get_session(session_id)
        conversation_state = dict(session.conversation_state)
        if MESSAGE_HISTORY_KEY in conversation_state:
            conversation_state[MESSAGE_HISTORY_KEY] = get_message_history(session)
        return SessionSnapshot(
            session_id=session.session_id,
            conversation_state=conversation_state,
            task_registry=list(session.task_registry.values()),
            executor_capabilities=self._executor_capabilities_provider(),
            strategy_state=dict(session.strategy_state),
            pending_clarifications=list(session.pending_clarifications),
            last_sequence=session.last_sequence,
            timestamp=utc_now(),
        )

    async def publish(
        self,
        session_id: str,
        category: StreamCategory,
        event_type: str,
        source: str,
        payload: dict,
        *,
        related_task_id: str | None = None,
        related_message_id: str | None = None,
    ) -> StreamEvent:
        return await self._publish(
            session_id,
            category,
            event_type,
            source,
            payload,
            persist=True,
            related_task_id=related_task_id,
            related_message_id=related_message_id,
        )

    async def publish_transient(
        self,
        session_id: str,
        category: StreamCategory,
        event_type: str,
        source: str,
        payload: dict,
        *,
        related_task_id: str | None = None,
        related_message_id: str | None = None,
    ) -> StreamEvent:
        return await self._publish(
            session_id,
            category,
            event_type,
            source,
            payload,
            persist=False,
            related_task_id=related_task_id,
            related_message_id=related_message_id,
        )

    async def _publish(
        self,
        session_id: str,
        category: StreamCategory,
        event_type: str,
        source: str,
        payload: dict,
        *,
        persist: bool,
        related_task_id: str | None = None,
        related_message_id: str | None = None,
    ) -> StreamEvent:
        session = self.get_session(session_id)
        session.last_sequence += 1
        event = StreamEvent(
            sequence=session.last_sequence,
            stream_event_id=new_id("stream"),
            session_id=session_id,
            category=category,
            event_type=event_type,
            source=source,
            related_task_id=related_task_id,
            related_message_id=related_message_id,
            timestamp=utc_now(),
            payload=payload,
        )
        if persist:
            session.event_log.append(event)
        for queue in list(session.subscribers):
            await queue.put(event)
        return event

    async def publish_snapshot(self, session_id: str) -> StreamEvent:
        snapshot = self.snapshot(session_id)
        return await self.publish(
            session_id,
            StreamCategory.SYSTEM,
            "session_snapshot",
            "system",
            snapshot.model_dump(mode="json"),
        )

    def add_pending_clarification(
        self, session_id: str, action: ConversationAction
    ) -> None:
        session = self.get_session(session_id)
        session.pending_clarifications.append(action)

    def clear_pending_clarifications(self, session_id: str) -> None:
        session = self.get_session(session_id)
        session.pending_clarifications.clear()

    def subscribe(self, session_id: str) -> asyncio.Queue:
        session = self.get_session(session_id)
        queue: asyncio.Queue = asyncio.Queue()
        session.subscribers.append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        session = self.get_session(session_id)
        if queue in session.subscribers:
            session.subscribers.remove(queue)
