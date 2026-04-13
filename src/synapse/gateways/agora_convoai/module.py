from __future__ import annotations

from contextlib import asynccontextmanager
import json
import time
from typing import Any, AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from synapse.gateways.base import (
    BaseGatewayModule,
    GatewayBindingRegistry,
    HttpSynapseGatewayTransport,
    SynapseGatewayError,
)

from .models import (
    ChatCompletionRequest,
    GatewayConfigResponse,
    GatewaySessionActivateRequest,
    GatewaySessionActivateResponse,
    GatewaySessionPrepareRequest,
    GatewaySessionPrepareResponse,
    GatewaySessionStopRequest,
    GatewaySessionStopResponse,
)
from .service import (
    AGORA_CONVOAI_IMPLEMENTATION_VERSION,
    AGORA_CONVOAI_SDK_LOADER_SIGNATURE,
    AgoraSDKConvoAIService,
    ConvoAIConfigurationError,
    ConvoAIRuntimeError,
)
from .session_service import AgoraGatewaySessionService
from .settings import AgoraConvoAIGatewaySettings, load_agora_gateway_settings


class AgoraConvoAIGatewayModule(BaseGatewayModule):
    slug = "agora-convoai"

    def __init__(self, settings: AgoraConvoAIGatewaySettings | None = None) -> None:
        self._settings = settings or load_agora_gateway_settings()

    def build_router(self) -> APIRouter:
        settings = self._settings
        transport = HttpSynapseGatewayTransport(
            settings.synapse_base_url,
            request_timeout_seconds=settings.request_timeout_seconds,
        )
        service = AgoraSDKConvoAIService(settings)
        binding_registry = GatewayBindingRegistry(transport, speaker=service)
        session_service = AgoraGatewaySessionService(
            binding_registry,
            settings,
            convoai_service=service,
        )

        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            try:
                yield
            finally:
                await binding_registry.close()
                await transport.close()

        router = APIRouter(
            prefix="/gateway/agora-convoai",
            tags=["gateway:agora-convoai"],
            lifespan=lifespan,
        )

        @router.get("/health")
        async def health() -> dict[str, object]:
            return {
                "status": "ok",
                "implementation_version": AGORA_CONVOAI_IMPLEMENTATION_VERSION,
                "sdk_loader_signature": list(AGORA_CONVOAI_SDK_LOADER_SIGNATURE),
                "synapse_base_url": settings.synapse_base_url,
                "upstream_transport_mode": "direct",
            }

        @router.get("/config", response_model=GatewayConfigResponse)
        async def config() -> GatewayConfigResponse:
            return session_service.get_config()

        @router.post("/sessions/prepare", response_model=GatewaySessionPrepareResponse)
        async def prepare_session(
            payload: GatewaySessionPrepareRequest,
        ) -> GatewaySessionPrepareResponse:
            try:
                return await session_service.prepare_session(payload)
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.post("/sessions/activate", response_model=GatewaySessionActivateResponse)
        async def activate_session(
            payload: GatewaySessionActivateRequest,
        ) -> GatewaySessionActivateResponse:
            try:
                return await session_service.activate_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except SynapseGatewayError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

        @router.post("/sessions/stop", response_model=GatewaySessionStopResponse)
        async def stop_session(
            payload: GatewaySessionStopRequest,
        ) -> GatewaySessionStopResponse:
            try:
                return await session_service.stop_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.post("/chat/completions")
        async def chat_completions(
            payload: ChatCompletionRequest,
            request: Request,
        ):
            binding_id = _resolve_binding_id(request)
            binding = binding_registry.get(binding_id)
            if binding is None:
                raise HTTPException(status_code=404, detail="Unknown gateway binding.")

            user_text = _extract_latest_user_text(payload.messages)
            if user_text is None:
                raise HTTPException(status_code=400, detail="No user message found in messages.")

            if payload.stream:
                return StreamingResponse(
                    _stream_completion(
                        transport=transport,
                        synapse_session_id=binding.synapse_session_id,
                        user_text=user_text,
                        model_name=payload.model or settings.default_model,
                    ),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            try:
                result = await transport.send_message(binding.synapse_session_id, user_text)
                return JSONResponse(
                    _build_completion_response(
                        completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                        created=int(time.time()),
                        model_name=payload.model or settings.default_model,
                        reply_text=result.reply_text,
                    )
                )
            except SynapseGatewayError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        return router


def create_headless_app(settings: AgoraConvoAIGatewaySettings | None = None) -> FastAPI:
    app = FastAPI(title="Synapse Agora ConvoAI Gateway")
    app.include_router(AgoraConvoAIGatewayModule(settings=settings).build_router())
    return app


async def _stream_completion(
    *,
    transport: HttpSynapseGatewayTransport,
    synapse_session_id: str,
    user_text: str,
    model_name: str,
) -> AsyncIterator[str]:
    request_id = f"agora-chat-{uuid4().hex[:8]}"
    completion_id = f"chatcmpl-{uuid4().hex[:8]}"
    created = int(time.time())
    role_sent = False
    try:
        async for event in transport.stream_message(
            synapse_session_id,
            user_text,
            request_id=request_id,
        ):
            event_type = event.get("type")
            if event_type == "assistant_response_started":
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
            if event_type == "assistant_response_delta":
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
                        delta={"content": str(event.get("delta") or "")},
                    )
                )
                continue
            if event_type == "assistant_response_completed":
                if not role_sent:
                    role_sent = True
                    yield _sse_payload(
                        _build_stream_chunk(
                            completion_id=completion_id,
                            created=created,
                            model_name=model_name,
                            delta={
                                "role": "assistant",
                                "content": str(event.get("reply_text") or ""),
                            },
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
            if event_type == "assistant_response_failed":
                if not role_sent:
                    role_sent = True
                    yield _sse_payload(
                        _build_stream_chunk(
                            completion_id=completion_id,
                            created=created,
                            model_name=model_name,
                            delta={
                                "role": "assistant",
                                "content": str(event.get("message") or ""),
                            },
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
        yield "data: [DONE]\n\n"
    except SynapseGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _resolve_binding_id(request: Request) -> str:
    binding_id = request.query_params.get("binding_id")
    if binding_id:
        return binding_id
    header = request.headers.get("x-binding-id")
    if header:
        return header
    raise HTTPException(status_code=400, detail="Missing binding_id.")


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
