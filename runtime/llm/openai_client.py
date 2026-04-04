from __future__ import annotations

from collections.abc import AsyncIterator
import inspect
from time import perf_counter
from typing import Any

from pydantic import BaseModel

from runtime.infrastructure.config import Settings
from runtime.llm.errors import LLMConfigurationError, LLMInvocationError
from runtime.llm.render_result import LLMResponseDetails, LLMResponseStreamEvent
from runtime.protocols.trace import TraceStage
from runtime.shared_blackboard.trace_state import TraceStateStore


class OpenAIProvider:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client if client is not None else self._build_client()

    def _build_client(self) -> Any | None:
        if not self._settings.openai_api_key:
            raise LLMConfigurationError(
                "OpenAI configuration is required. Set OPENAI_API_KEY before starting Synopse."
            )

        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {
            "api_key": self._settings.openai_api_key,
            "timeout": self._settings.openai_timeout_seconds,
        }
        if self._settings.openai_base_url:
            kwargs["base_url"] = self._settings.openai_base_url
        return AsyncOpenAI(**kwargs)

    def _require_client(self) -> Any:
        if self._client is None:
            raise LLMConfigurationError("OpenAI provider is not available.")
        return self._client

    async def _await_if_needed(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def _emit_trace(
        self,
        trace_state_store: TraceStateStore | None,
        *,
        session_id: str | None,
        stage: TraceStage,
        event_type: str,
        source_module: str,
        payload: dict[str, Any],
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> None:
        if trace_state_store is None or session_id is None:
            return
        await trace_state_store.publish(
            session_id,
            stage,
            event_type,
            source_module,
            payload,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )

    def _elapsed_ms(self, started_at: float, finished_at: float | None = None) -> int:
        end_time = perf_counter() if finished_at is None else finished_at
        return max(0, int(round((end_time - started_at) * 1000)))

    async def parse_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema: type[BaseModel],
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> BaseModel:
        client = self._require_client()
        await self._emit_trace(
            trace_state_store,
            session_id=session_id,
            stage=TraceStage.MESSAGE_INTERPRETER,
            event_type="llm_interpreter_request",
            source_module="openai_provider",
            payload={
                "model": self._settings.openai_model,
                "instructions": instructions,
                "input": input_text,
                "schema_name": schema.__name__,
            },
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )
        request_started_at = perf_counter()
        try:
            response = await self._await_if_needed(
                client.responses.parse(
                    model=self._settings.openai_model,
                    instructions=instructions,
                    input=input_text,
                    text_format=schema,
                )
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                raise LLMInvocationError("OpenAI did not return a structured output payload.")
            if isinstance(parsed, BaseModel):
                parsed_output: Any = parsed.model_dump(mode="json")
            else:
                parsed_output = parsed
            await self._emit_trace(
                trace_state_store,
                session_id=session_id,
                stage=TraceStage.MESSAGE_INTERPRETER,
                event_type="llm_interpreter_response",
                source_module="openai_provider",
                payload={
                    "model": self._settings.openai_model,
                    "parsed_output": parsed_output,
                    "duration_ms": self._elapsed_ms(request_started_at),
                },
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
            return parsed
        except Exception as exc:  # pragma: no cover
            await self._emit_trace(
                trace_state_store,
                session_id=session_id,
                stage=TraceStage.MESSAGE_INTERPRETER,
                event_type="llm_interpreter_error",
                source_module="openai_provider",
                payload={
                    "model": self._settings.openai_model,
                    "error": str(exc),
                    "duration_ms": self._elapsed_ms(request_started_at),
                },
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
            if isinstance(exc, LLMInvocationError):
                raise
            raise LLMInvocationError(f"OpenAI structured call failed: {exc}") from exc

    async def _render_text_result(
        self,
        *,
        instructions: str,
        input_text: str,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
        emit_trace: bool = True,
    ) -> LLMResponseDetails:
        client = self._require_client()
        if emit_trace:
            await self._emit_trace(
                trace_state_store,
                session_id=session_id,
                stage=TraceStage.RESPONSE_GENERATOR,
                event_type="llm_response_request",
                source_module="openai_provider",
                payload={
                    "model": self._settings.openai_model,
                    "instructions": instructions,
                    "input": input_text,
                },
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
        request_started_at = perf_counter()
        try:
            response = await self._await_if_needed(
                client.responses.create(
                    model=self._settings.openai_model,
                    instructions=instructions,
                    input=input_text,
                )
            )
            output_text = getattr(response, "output_text", None)
            if not output_text:
                raise LLMInvocationError("OpenAI did not return any output text.")
            rendered_text = str(output_text).strip()
            result = LLMResponseDetails(
                output_text=rendered_text,
                duration_ms=self._elapsed_ms(request_started_at),
                streamed=False,
            )
            if emit_trace:
                await self._emit_trace(
                    trace_state_store,
                    session_id=session_id,
                    stage=TraceStage.RESPONSE_GENERATOR,
                    event_type="llm_response_response",
                    source_module="openai_provider",
                    payload={
                        "model": self._settings.openai_model,
                        **result.to_trace_payload(),
                    },
                    span_id=span_id,
                    related_message_id=related_message_id,
                    related_task_id=related_task_id,
                )
            return result
        except Exception as exc:  # pragma: no cover
            if emit_trace:
                await self._emit_trace(
                    trace_state_store,
                    session_id=session_id,
                    stage=TraceStage.RESPONSE_GENERATOR,
                    event_type="llm_response_error",
                    source_module="openai_provider",
                    payload={
                        "model": self._settings.openai_model,
                        "error": str(exc),
                        "duration_ms": self._elapsed_ms(request_started_at),
                    },
                    span_id=span_id,
                    related_message_id=related_message_id,
                    related_task_id=related_task_id,
                )
            if isinstance(exc, LLMInvocationError):
                raise
            raise LLMInvocationError(f"OpenAI text generation failed: {exc}") from exc

    async def render_text_result(
        self,
        *,
        instructions: str,
        input_text: str,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> LLMResponseDetails:
        return await self._render_text_result(
            instructions=instructions,
            input_text=input_text,
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
            emit_trace=True,
        )

    async def render_text(
        self,
        *,
        instructions: str,
        input_text: str,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> str:
        result = await self.render_text_result(
            instructions=instructions,
            input_text=input_text,
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )
        return result.output_text

    async def stream_text_result(
        self,
        *,
        instructions: str,
        input_text: str,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> AsyncIterator[LLMResponseStreamEvent]:
        client = self._require_client()
        await self._emit_trace(
            trace_state_store,
            session_id=session_id,
            stage=TraceStage.RESPONSE_GENERATOR,
            event_type="llm_response_stream_request",
            source_module="openai_provider",
            payload={
                "model": self._settings.openai_model,
                "instructions": instructions,
                "input": input_text,
            },
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        )
        request_started_at = perf_counter()

        if not hasattr(client.responses, "stream"):
            result = await self._render_text_result(
                instructions=instructions,
                input_text=input_text,
                trace_state_store=None,
                session_id=None,
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
                emit_trace=False,
            )
            await self._emit_trace(
                trace_state_store,
                session_id=session_id,
                stage=TraceStage.RESPONSE_GENERATOR,
                event_type="llm_response_stream_response",
                source_module="openai_provider",
                payload={
                    "model": self._settings.openai_model,
                    **result.to_trace_payload(),
                },
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
            yield LLMResponseStreamEvent(delta=result.output_text)
            yield LLMResponseStreamEvent(delta="", is_final=True, metadata=result)
            return

        chunks: list[str] = []
        first_delta_at: float | None = None
        try:
            stream_manager = client.responses.stream(
                model=self._settings.openai_model,
                instructions=instructions,
                input=input_text,
            )
            final_text = ""
            if hasattr(stream_manager, "__aenter__"):
                async with stream_manager as stream:
                    async for event in stream:
                        if event.type == "response.output_text.delta":
                            delta = str(event.delta)
                            if delta:
                                if first_delta_at is None:
                                    first_delta_at = perf_counter()
                                chunks.append(delta)
                                yield LLMResponseStreamEvent(delta=delta)
                        elif event.type == "response.output_text.done":
                            final_text = event.text
            else:
                with stream_manager as stream:
                    for event in stream:
                        if event.type == "response.output_text.delta":
                            delta = str(event.delta)
                            if delta:
                                if first_delta_at is None:
                                    first_delta_at = perf_counter()
                                chunks.append(delta)
                                yield LLMResponseStreamEvent(delta=delta)
                        elif event.type == "response.output_text.done":
                            final_text = event.text
            final_text = final_text or "".join(chunks)
            if not final_text:
                raise LLMInvocationError("OpenAI did not return any streamed output text.")
            result = LLMResponseDetails(
                output_text=final_text,
                streamed=True,
                duration_ms=self._elapsed_ms(request_started_at),
                ttfb_ms=(
                    self._elapsed_ms(request_started_at, first_delta_at)
                    if first_delta_at is not None
                    else None
                ),
            )
            await self._emit_trace(
                trace_state_store,
                session_id=session_id,
                stage=TraceStage.RESPONSE_GENERATOR,
                event_type="llm_response_stream_response",
                source_module="openai_provider",
                payload={
                    "model": self._settings.openai_model,
                    **result.to_trace_payload(),
                },
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
            yield LLMResponseStreamEvent(delta="", is_final=True, metadata=result)
        except Exception as exc:  # pragma: no cover
            await self._emit_trace(
                trace_state_store,
                session_id=session_id,
                stage=TraceStage.RESPONSE_GENERATOR,
                event_type="llm_response_stream_error",
                source_module="openai_provider",
                payload={
                    "model": self._settings.openai_model,
                    "error": str(exc),
                    "duration_ms": self._elapsed_ms(request_started_at),
                },
                span_id=span_id,
                related_message_id=related_message_id,
                related_task_id=related_task_id,
            )
            if isinstance(exc, LLMInvocationError):
                raise
            raise LLMInvocationError(f"OpenAI streamed text generation failed: {exc}") from exc

    async def stream_text(
        self,
        *,
        instructions: str,
        input_text: str,
        trace_state_store: TraceStateStore | None = None,
        session_id: str | None = None,
        span_id: str | None = None,
        related_message_id: str | None = None,
        related_task_id: str | None = None,
    ) -> AsyncIterator[str]:
        async for event in self.stream_text_result(
            instructions=instructions,
            input_text=input_text,
            trace_state_store=trace_state_store,
            session_id=session_id,
            span_id=span_id,
            related_message_id=related_message_id,
            related_task_id=related_task_id,
        ):
            if event.is_final:
                continue
            yield event.delta
