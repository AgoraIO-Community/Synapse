from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from runtime.infrastructure.ids import new_id
from runtime.infrastructure.time import utc_now
from runtime.protocols.trace import TraceEvent, TraceSnapshot, TraceStage


@dataclass(slots=True)
class TraceSessionState:
    session_id: str
    trace_log: list[TraceEvent] = field(default_factory=list)
    last_trace_sequence: int = 0
    subscribers: list[asyncio.Queue] = field(default_factory=list)


class TraceStateStore:
    def __init__(self) -> None:
        self._sessions: dict[str, TraceSessionState] = {}

    def ensure_session(self, session_id: str) -> TraceSessionState:
        session = self._sessions.get(session_id)
        if session is None:
            session = TraceSessionState(session_id=session_id)
            self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> TraceSessionState:
        if session_id not in self._sessions:
            raise KeyError(f"Unknown trace session: {session_id}")
        return self._sessions[session_id]

    def snapshot(self, session_id: str) -> TraceSnapshot:
        session = self.ensure_session(session_id)
        return TraceSnapshot(
            session_id=session_id,
            recent_traces=list(session.trace_log[-50:]),
            last_trace_sequence=session.last_trace_sequence,
            timestamp=utc_now(),
        )

    async def publish(
        self,
        session_id: str,
        stage: TraceStage,
        event_type: str,
        source_module: str,
        payload: dict,
        *,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> TraceEvent:
        session = self.ensure_session(session_id)
        session.last_trace_sequence += 1
        event = TraceEvent(
            trace_sequence=session.last_trace_sequence,
            trace_event_id=new_id("trace"),
            session_id=session_id,
            stage=stage,
            event_type=event_type,
            source_module=source_module,
            span_id=span_id,
            parent_span_id=parent_span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
            timestamp=utc_now(),
            payload=payload,
        )
        session.trace_log.append(event)
        for queue in list(session.subscribers):
            await queue.put(event)
        return event

    async def publish_snapshot(self, session_id: str) -> TraceEvent:
        snapshot = self.snapshot(session_id)
        return await self.publish(
            session_id,
            TraceStage.RUNTIME_STATE,
            "trace_snapshot",
            "trace_state",
            snapshot.model_dump(mode="json"),
        )

    def subscribe(self, session_id: str) -> asyncio.Queue:
        session = self.ensure_session(session_id)
        queue: asyncio.Queue = asyncio.Queue()
        session.subscribers.append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        session = self.ensure_session(session_id)
        if queue in session.subscribers:
            session.subscribers.remove(queue)
