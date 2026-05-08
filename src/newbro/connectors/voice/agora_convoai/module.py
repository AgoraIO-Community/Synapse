from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import re
import time
from typing import Any, AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from newbro.api.auth import require_http_api_auth
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

logger = logging.getLogger(__name__)


class _VoiceTranscriptStore:
    def __init__(self, *, per_session_limit: int = 200) -> None:
        self._per_session_limit = per_session_limit
        self._turns_by_session: dict[str, list[dict[str, object]]] = {}
        self._last_ts = 0
        self._last_user_text_by_session: dict[str, str] = {}

    def append(self, session_id: str, *, speaker: str, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        ts = max(int(time.time() * 1000), self._last_ts + 1)
        self._last_ts = ts
        turns = self._turns_by_session.setdefault(session_id, [])
        turns.append(
            {
                "id": f"{speaker}-{uuid4().hex[:8]}",
                "speaker": speaker,
                "text": cleaned,
                "ts": ts,
            }
        )
        if len(turns) > self._per_session_limit:
            del turns[:-self._per_session_limit]

    def since(self, session_id: str, *, since: int) -> dict[str, object]:
        turns = self._turns_by_session.get(session_id, [])
        filtered = [turn for turn in turns if int(turn["ts"]) > since]
        latest_ts = int(filtered[-1]["ts"]) if filtered else since
        return {"turns": filtered, "latest_ts": latest_ts}

    def next_user_delta(self, session_id: str, raw_text: str) -> str | None:
        cleaned = _normalize_user_source_text(raw_text)
        if not cleaned:
            return None
        previous = self._last_user_text_by_session.get(session_id)
        self._last_user_text_by_session[session_id] = cleaned
        if previous is None:
            return cleaned
        if cleaned == previous:
            return None
        if cleaned.startswith(previous):
            delta = cleaned[len(previous):].strip()
            return delta or None
        overlap = _longest_suffix_prefix_overlap(previous, cleaned)
        if overlap > 0:
            delta = cleaned[overlap:].strip()
            return delta or None
        return cleaned


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
        transcript_store = _VoiceTranscriptStore()
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
        async def config(request: Request) -> ConnectorConfigResponse:
            require_http_api_auth(request)
            return session_service.get_config()

        @router.post("/sessions/prepare", response_model=ConnectorSessionPrepareResponse)
        async def prepare_session(
            payload: ConnectorSessionPrepareRequest,
            request: Request,
        ) -> ConnectorSessionPrepareResponse:
            require_http_api_auth(request)
            try:
                return await session_service.prepare_session(payload)
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.post("/sessions/activate", response_model=ConnectorSessionActivateResponse)
        async def activate_session(
            payload: ConnectorSessionActivateRequest,
            request: Request,
        ) -> ConnectorSessionActivateResponse:
            require_http_api_auth(request)
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
            request: Request,
        ) -> ConnectorSessionStopResponse:
            require_http_api_auth(request)
            try:
                return await session_service.stop_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc


        @router.post("/stt/sessions/prepare", response_model=SttSessionPrepareResponse)
        async def prepare_stt_session(
            payload: SttSessionPrepareRequest,
            request: Request,
        ) -> SttSessionPrepareResponse:
            require_http_api_auth(request)
            try:
                return stt_service.prepare_session(payload)
            except ConvoAIConfigurationError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

        @router.post("/stt/sessions/start", response_model=SttSessionStartResponse)
        async def start_stt_session(
            payload: SttSessionStartRequest,
            request: Request,
        ) -> SttSessionStartResponse:
            require_http_api_auth(request)
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
            request: Request,
        ) -> SttSessionHeartbeatResponse:
            require_http_api_auth(request)
            try:
                return stt_service.heartbeat_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

        @router.post("/stt/sessions/leave", response_model=SttSessionStopResponse)
        async def leave_stt_session(
            payload: SttSessionLeaveRequest,
            request: Request,
        ) -> SttSessionStopResponse:
            require_http_api_auth(request)
            try:
                return await stt_service.leave_session(payload)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.get("/stt/sessions/{stt_session_id}", response_model=SttSessionQueryResponse)
        async def query_stt_session(stt_session_id: str, request: Request) -> SttSessionQueryResponse:
            require_http_api_auth(request)
            try:
                return await stt_service.query_session(stt_session_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ConvoAIRuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.post("/stt/sessions/stop", response_model=SttSessionStopResponse)
        async def stop_stt_session(
            payload: SttSessionStopRequest,
            request: Request,
        ) -> SttSessionStopResponse:
            require_http_api_auth(request)
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
            require_http_api_auth(request)
            binding_id = _resolve_binding_id(request)
            binding = binding_registry.get(binding_id)
            if binding is None:
                raise HTTPException(status_code=404, detail="Unknown connector binding.")

            raw_user_text = _extract_latest_user_text(payload.messages)
            if raw_user_text is None:
                logger.info(
                    "Agora chat/completions request had no explicit user turn; treating as no-op. messages=%s",
                    _summarize_messages(payload.messages),
                )
                if payload.stream:
                    return StreamingResponse(
                        _empty_stream_completion(
                            model_name=payload.model or AGORA_BRIDGE_MODEL,
                        ),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                    )
                return JSONResponse(
                    _build_completion_response(
                        completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                        created=int(time.time()),
                        model_name=payload.model or AGORA_BRIDGE_MODEL,
                        reply_text="",
                    )
                )
            user_text = transcript_store.next_user_delta(binding.synapse_session_id, raw_user_text)
            if user_text is None:
                logger.info(
                    "Agora chat/completions request produced no new user delta; treating as no-op. raw=%r",
                    raw_user_text,
                )
                if payload.stream:
                    return StreamingResponse(
                        _empty_stream_completion(
                            model_name=payload.model or AGORA_BRIDGE_MODEL,
                        ),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                    )
                return JSONResponse(
                    _build_completion_response(
                        completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                        created=int(time.time()),
                        model_name=payload.model or AGORA_BRIDGE_MODEL,
                        reply_text="",
                    )
                )
            transcript_store.append(binding.synapse_session_id, speaker="user", text=user_text)

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
                        transcript_store=transcript_store,
                    ),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            try:
                reply_text = await _complete_message(
                    transport=transport,
                    synapse_session_id=binding.synapse_session_id,
                    user_text=user_text,
                    target_persona_id=target_persona_id,
                )
                transcript_store.append(binding.synapse_session_id, speaker="agent", text=reply_text)
                return JSONResponse(
                    _build_completion_response(
                        completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                        created=int(time.time()),
                        model_name=payload.model or AGORA_BRIDGE_MODEL,
                        reply_text=reply_text,
                    )
                )
            except NewbroConnectorError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @router.get("/voice-transcripts/{session_id}")
        async def voice_transcripts(
            session_id: str,
            request: Request,
        ) -> dict[str, object]:
            require_http_api_auth(request)
            raw_since = request.query_params.get("since", "0")
            try:
                since = int(raw_since)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="since must be an integer.") from exc
            return transcript_store.since(session_id, since=since)

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
    transcript_store: _VoiceTranscriptStore,
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid4().hex[:8]}"
    created = int(time.time())
    try:
        reply_text = await _complete_message(
            transport=transport,
            synapse_session_id=synapse_session_id,
            user_text=user_text,
            target_persona_id=target_persona_id,
        )
        transcript_store.append(synapse_session_id, speaker="agent", text=reply_text)
        yield _sse_payload(
            _build_stream_chunk(
                completion_id=completion_id,
                created=created,
                model_name=model_name,
                delta={"role": "assistant"},
            )
        )
        if reply_text:
            yield _sse_payload(
                _build_stream_chunk(
                    completion_id=completion_id,
                    created=created,
                    model_name=model_name,
                    delta={"content": reply_text},
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


async def _empty_stream_completion(*, model_name: str) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid4().hex[:8]}"
    created = int(time.time())
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


async def _complete_message(
    *,
    transport: HttpNewbroConnectorTransport,
    synapse_session_id: str,
    user_text: str,
    target_persona_id: str | None,
) -> str:
    result = await transport.send_message(
        synapse_session_id,
        user_text,
        target_persona_id=target_persona_id,
        timeout_seconds=60.0,
    )
    reply_text = result.reply_text.strip()
    if reply_text:
        return reply_text
    raise NewbroConnectorError("Newbro did not return assistant reply text.")

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
        role = message.get("role")
        normalized_role = role.strip().lower() if isinstance(role, str) else None
        if normalized_role != "user":
            continue
        text = _extract_message_text(
            message.get("content")
            if "content" in message
            else message.get("text", message.get("input"))
        )
        if text:
            return text
    return None


def _extract_message_text(content: object) -> str | None:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            extracted = _extract_message_text(item)
            if extracted:
                parts.append(extracted)
        return "\n".join(parts) if parts else None
    if isinstance(content, dict):
        for key in ("text", "value", "content", "input_text", "input", "message", "transcript"):
            if key not in content:
                continue
            extracted = _extract_message_text(content.get(key))
            if extracted:
                return extracted
    return None


def _summarize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    summary: list[dict[str, str | None]] = []
    for message in messages:
        summary.append(
            {
                "role": str(message.get("role")) if message.get("role") is not None else None,
                "text": (_extract_message_text(message.get("content")) or _extract_message_text(message.get("text")) or "")[:120],
            }
        )
    return summary


def _looks_like_agent_greeting_echo(text: str) -> bool:
    normalized = " ".join(text.strip().lower().split())
    return normalized in {
        "can i help you?",
        "can i help you？",
        "hello. how can i help you today?",
        "hello. how can i help you today？",
        "how can i help you today?",
        "how can i help you today？",
    }


def _normalize_user_source_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    cleaned = _strip_leading_greeting_echo(cleaned)
    return cleaned.strip()


def _strip_leading_greeting_echo(text: str) -> str:
    patterns = (
        r"^\s*can i help you[?？!.。]*\s*",
        r"^\s*hello\.?\s*how can i help you today[?？!.。]*\s*",
        r"^\s*how can i help you today[?？!.。]*\s*",
    )
    stripped = text
    changed = True
    while changed:
        changed = False
        for pattern in patterns:
            next_value, count = re.subn(pattern, "", stripped, flags=re.IGNORECASE)
            if count > 0:
                stripped = next_value
                changed = True
    return stripped


def _longest_suffix_prefix_overlap(previous: str, current: str) -> int:
    max_len = min(len(previous), len(current))
    for length in range(max_len, 0, -1):
        if previous[-length:] == current[:length]:
            return length
    return 0


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
