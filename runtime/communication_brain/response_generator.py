from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from runtime.llm.render_result import LLMResponseDetails
from runtime.llm.responder import ResponseClient
from runtime.protocols.conversation import ConversationAction
from runtime.shared_blackboard.trace_state import TraceStateStore


@dataclass(slots=True)
class ResponseTextChunk:
    delta: str
    text: str
    is_final: bool = False
    metadata: LLMResponseDetails | None = None


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
    ) -> tuple[ConversationAction, LLMResponseDetails | None]:
        if not action.render_text:
            action.render_text, metadata = await self._responder.render_result(
                action,
                trace_state_store=trace_state_store,
                session_id=session_id,
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
            return action, metadata
        return action, None

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
        async for event in self._responder.stream_render_result(
            action,
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        ):
            if event.is_final:
                action.render_text = (
                    event.metadata.output_text if event.metadata is not None else "".join(chunks)
                )
                yield ResponseTextChunk(
                    delta="",
                    text=action.render_text,
                    is_final=True,
                    metadata=event.metadata,
                )
                return

            if not event.delta:
                continue

            chunks.append(event.delta)
            yield ResponseTextChunk(
                delta=event.delta,
                text="".join(chunks),
                is_final=False,
            )

        action.render_text = "".join(chunks)
        yield ResponseTextChunk(
            delta="",
            text=action.render_text,
            is_final=True,
        )
