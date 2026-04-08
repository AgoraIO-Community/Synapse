from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from synopse.runtime import RuntimeContainer, build_runtime_container

from .bridge import BridgeRegistry, DuplicateBindingError, MissingRegistrationConfigError
from .convoai_service import AgoraSDKConvoAIService
from .frontend_adapter import (
    ConvoAIConfigurationError,
    ConvoAIRuntimeError,
    FrontendSessionService,
)
from .models import (
    ChatCompletionRequest,
    FrontendConfigResponse,
    FrontendSessionActivateRequest,
    FrontendSessionActivateResponse,
    FrontendSessionPrepareRequest,
    FrontendSessionPrepareResponse,
    FrontendSessionStopRequest,
    FrontendSessionStopResponse,
    HealthResponse,
)
from .settings import AgoraBridgeSettings, load_bridge_settings
from .settings import configure_example_env


def create_app(
    *,
    runtime_container: RuntimeContainer | None = None,
    bridge_settings: AgoraBridgeSettings | None = None,
    bridge_registry: BridgeRegistry | None = None,
    frontend_service: FrontendSessionService | None = None,
) -> FastAPI:
    configure_example_env()
    settings = bridge_settings or load_bridge_settings()
    container = runtime_container or build_runtime_container()
    convoai_service = AgoraSDKConvoAIService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await app.state.bridge_registry.close()

    app = FastAPI(title="Synopse Agora ConvoAI Bridge", lifespan=lifespan)
    app.state.runtime_container = container
    app.state.bridge_settings = settings
    app.state.bridge_registry = bridge_registry or BridgeRegistry(container, speaker=convoai_service)
    app.state.frontend_service = frontend_service or FrontendSessionService(
        app.state.bridge_registry,
        settings,
        convoai_service=convoai_service,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/frontend/config", response_model=FrontendConfigResponse)
    async def frontend_config(request: Request) -> FrontendConfigResponse:
        service: FrontendSessionService = request.app.state.frontend_service
        return service.get_config()

    @app.post("/frontend/session/prepare", response_model=FrontendSessionPrepareResponse)
    async def frontend_session_prepare(
        payload: FrontendSessionPrepareRequest,
        request: Request,
    ) -> FrontendSessionPrepareResponse:
        service: FrontendSessionService = request.app.state.frontend_service
        try:
            return await service.prepare_session(payload)
        except ConvoAIConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ConvoAIRuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/frontend/session/activate", response_model=FrontendSessionActivateResponse)
    async def frontend_session_activate(
        payload: FrontendSessionActivateRequest,
        request: Request,
    ) -> FrontendSessionActivateResponse:
        service: FrontendSessionService = request.app.state.frontend_service
        try:
            return await service.activate_session(payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConvoAIConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ConvoAIRuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except DuplicateBindingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except MissingRegistrationConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/frontend/session/stop", response_model=FrontendSessionStopResponse)
    async def frontend_session_stop(
        payload: FrontendSessionStopRequest,
        request: Request,
    ) -> FrontendSessionStopResponse:
        service: FrontendSessionService = request.app.state.frontend_service
        try:
            return await service.stop_session(payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConvoAIRuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/chat/completions")
    async def chat_completions(
        payload: ChatCompletionRequest,
        request: Request,
    ):
        bridge_session_id = _resolve_bridge_session_id(request)
        registry: BridgeRegistry = request.app.state.bridge_registry
        binding = registry.get(bridge_session_id)
        if binding is None:
            raise HTTPException(status_code=404, detail="Unknown bridge session.")

        container: RuntimeContainer = request.app.state.runtime_container
        try:
            session = container.get_session(binding.synopse_session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        user_text = _extract_latest_user_text(payload.messages)
        if user_text is None:
            raise HTTPException(status_code=400, detail="No user message found in messages.")

        if payload.stream:
            return StreamingResponse(
                _stream_completion(
                    session=session,
                    user_text=user_text,
                    model_name=payload.model or request.app.state.bridge_settings.default_model,
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        request_id = f"agora-chat-{uuid4().hex[:8]}"
        _, completion = await session.submit_message(
            request_id,
            user_text,
            start_processing=False,
        )
        session.start_message_processing()
        result = await completion
        return JSONResponse(
            _build_completion_response(
                completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                created=int(time.time()),
                model_name=payload.model or request.app.state.bridge_settings.default_model,
                reply_text=result.reply_text,
            )
        )

    return app


async def _stream_completion(
    *,
    session,
    user_text: str,
    model_name: str,
) -> AsyncIterator[str]:
    queue = session.subscribe()
    request_id = f"agora-chat-{uuid4().hex[:8]}"
    completion_id = f"chatcmpl-{uuid4().hex[:8]}"
    created = int(time.time())
    role_sent = False
    try:
        _, completion = await session.submit_message(
            request_id,
            user_text,
            start_processing=False,
        )
        session.start_message_processing()
        while True:
            event = await queue.get()
            if getattr(event, "request_id", None) != request_id:
                continue
            if event.type == "assistant_response_started":
                if not role_sent:
                    role_sent = True
                    yield _sse_payload(
                        _build_stream_chunk(
                            completion_id=completion_id,
                            created=created,
                            model_name=model_name,
                            delta={"role": "assistant"},
                        )
                    )
                continue
            if event.type == "assistant_response_delta":
                if not role_sent:
                    role_sent = True
                    yield _sse_payload(
                        _build_stream_chunk(
                            completion_id=completion_id,
                            created=created,
                            model_name=model_name,
                            delta={"role": "assistant"},
                        )
                    )
                yield _sse_payload(
                    _build_stream_chunk(
                        completion_id=completion_id,
                        created=created,
                        model_name=model_name,
                        delta={"content": event.delta},
                    )
                )
                continue
            if event.type == "assistant_response_completed":
                if not role_sent:
                    role_sent = True
                    yield _sse_payload(
                        _build_stream_chunk(
                            completion_id=completion_id,
                            created=created,
                            model_name=model_name,
                            delta={"role": "assistant", "content": event.reply_text},
                        )
                    )
                yield _sse_payload(
                    _build_stream_chunk(
                        completion_id=completion_id,
                        created=created,
                        model_name=model_name,
                        delta={},
                        finish_reason="stop",
                    )
                )
                break
            if event.type == "assistant_response_failed":
                if not role_sent:
                    role_sent = True
                    yield _sse_payload(
                        _build_stream_chunk(
                            completion_id=completion_id,
                            created=created,
                            model_name=model_name,
                            delta={"role": "assistant", "content": event.message},
                        )
                    )
                yield _sse_payload(
                    _build_stream_chunk(
                        completion_id=completion_id,
                        created=created,
                        model_name=model_name,
                        delta={},
                        finish_reason="stop",
                    )
                )
                break
        await completion
        yield "data: [DONE]\n\n"
    finally:
        session.unsubscribe(queue)


def _resolve_bridge_session_id(request: Request) -> str:
    bridge_session_id = request.query_params.get("bridge_session_id")
    if bridge_session_id:
        return bridge_session_id
    header = request.headers.get("x-bridge-session-id")
    if header:
        return header
    raise HTTPException(status_code=400, detail="Missing bridge_session_id.")


def _extract_latest_user_text(messages: list[dict[str, Any]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        text = _extract_message_text(message.get("content"))
        if text:
            return text
    return None


def _extract_message_text(content: object) -> str | None:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            stripped = text.strip()
            if stripped:
                parts.append(stripped)
            continue
        if isinstance(text, dict):
            value = text.get("value")
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
    if not parts:
        return None
    return "\n".join(parts)


def _build_completion_response(
    *,
    completion_id: str,
    created: int,
    model_name: str,
    reply_text: str,
) -> dict[str, object]:
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply_text,
                },
                "finish_reason": "stop",
            }
        ],
    }


def _build_stream_chunk(
    *,
    completion_id: str,
    created: int,
    model_name: str,
    delta: dict[str, object],
    finish_reason: str | None = None,
) -> dict[str, object]:
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def _sse_payload(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"


app = create_app()
