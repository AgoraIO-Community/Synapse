from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from runtime.llm.responder import ResponseClient
from runtime.protocols.conversation import ConversationAction
from runtime.shared_blackboard.trace_state import TraceStateStore


@dataclass(slots=True)
class ResponseTextChunk:
    delta: str
    text: str
    is_final: bool = False


class ResponseGenerator:
    def __init__(self, responder: ResponseClient) -> None:
        self._responder = responder

    async def finalize(
        self,
        action: ConversationAction,
        *,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> ConversationAction:
        if not action.render_text:
            action.render_text = await self._responder.render(
                action,
                trace_state_store=trace_state_store,
                session_id=session_id,
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
        return action

    async def stream_finalize(
        self,
        action: ConversationAction,
        *,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> AsyncIterator[ResponseTextChunk]:
        if action.render_text:
            yield ResponseTextChunk(delta="", text=action.render_text, is_final=True)
            return

        chunks: list[str] = []
        async for delta in self._responder.stream_render(
            action,
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        ):
            chunks.append(delta)
            yield ResponseTextChunk(
                delta=delta,
                text="".join(chunks),
                is_final=False,
            )

        action.render_text = "".join(chunks)
        yield ResponseTextChunk(
            delta="",
            text=action.render_text,
            is_final=True,
        )
