from __future__ import annotations

from contextlib import asynccontextmanager
import json
import time
from typing import Any, AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from newbro.api.paths import API_PREFIX, api_path
from newbro.connectors.base import (
    BaseConnectorModule,
    ConnectorBindingRegistry,
    HttpNewbroConnectorTransport,
    NewbroConnectorError,
)

from .models import (
    ChatCompletionRequest,
    ConnectorConfigResponse,
    ConnectorSessionActivateRequest,
    ConnectorSessionActivateResponse,
    ConnectorSessionPrepareRequest,
    ConnectorSessionPrepareResponse,
    ConnectorSessionStopRequest,
    ConnectorSessionStopResponse,
    SttSessionQueryResponse,
    SttSessionPrepareRequest,
    SttSessionPrepareResponse,
    SttSessionHeartbeatRequest,
    SttSessionHeartbeatResponse,
    SttSessionLeaveRequest,
    SttSessionStartRequest,
    SttSessionStartResponse,
    SttSessionStopRequest,
    SttSessionStopResponse,
)
from .service import (
    AGORA_CONVOAI_IMPLEMENTATION_VERSION,
    AGORA_CONVOAI_SDK_LOADER_SIGNATURE,
    AgoraSDKConvoAIService,
    ConvoAIConfigurationError,
    ConvoAIRuntimeError,
)
from .session_service import AgoraConnectorSessionService
from .stt_service import AgoraSttService
from .settings import AGORA_BRIDGE_MODEL, AgoraConvoAIConnectorSettings, load_agora_connector_settings


class AgoraConvoAIConnectorModule(BaseConnectorModule):
    slug = "agora-convoai"

    def __init__(self, settings: AgoraConvoAIConnectorSettings | None = None) -> None:
        self._settings = settings or load_agora_connector_settings()

    def build_router(self) -> APIRouter:
        settings = self._settings
        transport = HttpNewbroConnectorTransport(
            settings.synapse_base_url,
            request_timeout_seconds=settings.request_timeout_seconds,
            bearer_token=settings.synapse_api_bearer_token,
            cloudflare_access_client_id=settings.cloudflare_access_client_id,
            cloudflare_access_client_secret=settings.cloudflare_access_client_secret,
        )
        service = AgoraSDKConvoAIService(settings)
        stt_service = AgoraSttService(settings)
        binding_registry = ConnectorBindingRegistry(transport, speaker=service)
        session_service = AgoraConnectorSessionService(
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
                await stt_service.close()
                await transport.close()

        router = APIRouter(
            prefix=f"{API_PREFIX}/connectors/agora-convoai",
            tags=["connector:agora-convoai"],
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

        @router.get("/config", response_model=ConnectorConfigResponse)
        async def config() -> ConnectorConfigResponse:
            return session_service.get_config()

        @router.post("/sessions/prepare", response_model=ConnectorSessionPrepareResponse)
        async def prepare_session(
            payload: ConnectorSessionPrepareRequest,
        ) -> ConnectorSessionPrepareResponse:
            try:
                return await session_service.prepare_session(payload)
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.post("/sessions/activate", response_model=ConnectorSessionActivateResponse)
        async def activate_session(
            payload: ConnectorSessionActivateRequest,
        ) -> ConnectorSessionActivateResponse:
            try:
                return await session_service.activate_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except NewbroConnectorError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

        @router.post("/sessions/stop", response_model=ConnectorSessionStopResponse)
        async def stop_session(
            payload: ConnectorSessionStopRequest,
        ) -> ConnectorSessionStopResponse:
            try:
                return await session_service.stop_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc


        @router.post("/stt/sessions/prepare", response_model=SttSessionPrepareResponse)
        async def prepare_stt_session(
            payload: SttSessionPrepareRequest,
        ) -> SttSessionPrepareResponse:
            try:
                return stt_service.prepare_session(payload)
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

        @router.post("/stt/sessions/start", response_model=SttSessionStartResponse)
        async def start_stt_session(
            payload: SttSessionStartRequest,
        ) -> SttSessionStartResponse:
            try:
                return await stt_service.start_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.post("/stt/sessions/heartbeat", response_model=SttSessionHeartbeatResponse)
        async def heartbeat_stt_session(
            payload: SttSessionHeartbeatRequest,
        ) -> SttSessionHeartbeatResponse:
            try:
                return stt_service.heartbeat_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

        @router.post("/stt/sessions/leave", response_model=SttSessionStopResponse)
        async def leave_stt_session(
            payload: SttSessionLeaveRequest,
        ) -> SttSessionStopResponse:
            try:
                return await stt_service.leave_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.get("/stt/sessions/{stt_session_id}", response_model=SttSessionQueryResponse)
        async def query_stt_session(stt_session_id: str) -> SttSessionQueryResponse:
            try:
                return await stt_service.query_session(stt_session_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.post("/stt/sessions/stop", response_model=SttSessionStopResponse)
        async def stop_stt_session(
            payload: SttSessionStopRequest,
        ) -> SttSessionStopResponse:
            try:
                return await stt_service.stop_session(payload.stt_session_id)
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
                raise HTTPException(status_code=404, detail="Unknown connector binding.")

            user_text = _extract_latest_user_text(payload.messages)
            if user_text is None:
                raise HTTPException(status_code=400, detail="No user message found in messages.")

            # Read voice target persona from the live session if available.
            target_persona_id: str | None = None
            container = getattr(request.app.state, "runtime_container", None)
            if container is not None:
                try:
                    live_session = container.get_session(binding.synapse_session_id)
                    target_persona_id = live_session.voice_target_persona_id
                except (KeyError, AttributeError):
                    pass

            if payload.stream:
                return StreamingResponse(
                    _stream_completion(
                        transport=transport,
                        synapse_session_id=binding.synapse_session_id,
                        user_text=user_text,
                        model_name=payload.model or AGORA_BRIDGE_MODEL,
                        target_persona_id=target_persona_id,
                    ),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            try:
                await transport.submit_asr_turn(binding.synapse_session_id, user_text)
                return JSONResponse(
                    _build_completion_response(
                        completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                        created=int(time.time()),
                        model_name=payload.model or AGORA_BRIDGE_MODEL,
                        reply_text="Draft updated.",
                    )
                )
            except NewbroConnectorError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        return router


def create_headless_app(settings: AgoraConvoAIConnectorSettings | None = None) -> FastAPI:
    app = FastAPI(
        title="Newbro Agora ConvoAI Connector",
        openapi_url=api_path("/openapi.json"),
        docs_url=api_path("/docs"),
        redoc_url=api_path("/redoc"),
    )
    app.include_router(AgoraConvoAIConnectorModule(settings=settings).build_router())
    return app


async def _stream_completion(
    *,
    transport: HttpNewbroConnectorTransport,
    synapse_session_id: str,
    user_text: str,
    model_name: str,
    target_persona_id: str | None = None,
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid4().hex[:8]}"
    created = int(time.time())
    try:
        await transport.submit_asr_turn(synapse_session_id, user_text)
        yield _sse_payload(
            _build_stream_chunk(
                completion_id=completion_id,
                created=created,
                model_name=model_name,
                delta={"role": "assistant", "content": "Draft updated."},
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
        yield "data: [DONE]\n\n"
    except NewbroConnectorError as exc:
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
