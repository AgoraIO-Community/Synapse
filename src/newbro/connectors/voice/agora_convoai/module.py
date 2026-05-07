from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import os
import time
from typing import Any, AsyncIterator
from uuid import uuid4

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from openai import AsyncOpenAI

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


_logger = logging.getLogger(__name__)


# Default conversation-brain system prompt. Used only when the operator opts into
# the conversation-brain mode by setting `conversation_brain_prompt` in
# ~/.newbro/config.yaml. Kept short so it fits comfortably in every request.
_DEFAULT_CONVERSATION_BRAIN_PROMPT = (
    "You are Newbro's \"conversation brain\", talking with the user over a voice call. "
    "Your only job is to clarify the requirement together: what to build, why, scope, "
    "and acceptance criteria. You DO NOT write code, change files, or run commands — "
    "all execution is done by the executor brain (Codex) on the backend.\n\n"
    "Workflow (strict three phases):\n"
    "1. CLARIFY — keep replies to 1–2 short sentences, ask one focused question at a time.\n"
    "2. SUMMARISE — once the requirement is clear, restate it in a sentence or two and "
    "ask exactly: \"That is the spec to send to Codex. Confirm execute?\".\n"
    "3. WAIT — only treat the literal phrase \"confirm execute\" (or its localised "
    "equivalent) as authorisation to dispatch. Anything else means keep clarifying.\n\n"
    "Hard rules:\n"
    "- Never pretend you started writing code, opened files, or ran tests. Codex does that, not you.\n"
    "- Before the user says the confirmation phrase, never claim the task has been dispatched.\n"
    "- Reply in the user's language."
)


# Default trigger phrases. The exact match (after trimming punctuation) is required.
# English first; Chinese kept for parity since the upstream demo audience uses both.
_DEFAULT_DISPATCH_TRIGGER_PHRASES: tuple[str, ...] = ("confirm execute", "确认执行")


# In-memory bypass transcript store. Populated only when the conversation-brain
# mode is active. Lets the frontend poll the chat-completions in/out pairs that
# we already have on the backend, so the UI can show subtitles even when the
# Agora data channel (RTM/datastream) is unreliable for the operator's network.
# NOTE: single-process only — running multiple uvicorn workers would split the
# store and the frontend would see partial transcripts.
_VOICE_TRANSCRIPTS: dict[str, list[dict[str, object]]] = {}
_VOICE_TRANSCRIPT_LIMIT_PER_SESSION = 200
_VOICE_TRANSCRIPT_SESSION_TTL_SECONDS = 60 * 60  # 1h
_voice_transcript_last_gc: float = 0.0


def _gc_voice_transcripts(now: float) -> None:
    """Drop sessions whose newest entry is older than the TTL."""
    global _voice_transcript_last_gc
    if now - _voice_transcript_last_gc < 60.0:
        return
    _voice_transcript_last_gc = now
    expired = [
        sid for sid, bucket in _VOICE_TRANSCRIPTS.items()
        if not bucket
        or now - float(bucket[-1].get("ts", 0)) > _VOICE_TRANSCRIPT_SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _VOICE_TRANSCRIPTS.pop(sid, None)


def _push_voice_transcript(session_id: str, speaker: str, text: str) -> None:
    text_clean = (text or "").strip()
    if not text_clean:
        return
    now = time.time()
    _gc_voice_transcripts(now)
    bucket = _VOICE_TRANSCRIPTS.setdefault(session_id, [])
    bucket.append({
        "id": f"{int(now * 1000)}-{uuid4().hex[:6]}",
        "speaker": speaker,  # "user" | "agent"
        "text": text_clean,
        "ts": now,
    })
    if len(bucket) > _VOICE_TRANSCRIPT_LIMIT_PER_SESSION:
        del bucket[: len(bucket) - _VOICE_TRANSCRIPT_LIMIT_PER_SESSION]


def _conversation_brain_enabled(settings: AgoraConvoAIConnectorSettings) -> bool:
    """The new LLM-proxy / dispatch-trigger pipeline only runs when the operator
    explicitly configures a conversation-brain prompt. Otherwise we keep the
    legacy behaviour of forwarding the user's STT to the draft pipeline and
    replying \"Draft updated.\"."""
    return bool((settings.conversation_brain_prompt or "").strip())


def _conversation_brain_prompt(settings: AgoraConvoAIConnectorSettings) -> str:
    custom = (settings.conversation_brain_prompt or "").strip()
    return custom or _DEFAULT_CONVERSATION_BRAIN_PROMPT


def _dispatch_trigger_phrases(settings: AgoraConvoAIConnectorSettings) -> tuple[str, ...]:
    raw = (settings.dispatch_trigger_phrases or "").strip()
    if not raw:
        return _DEFAULT_DISPATCH_TRIGGER_PHRASES
    return tuple(p.strip().lower() for p in raw.split(",") if p.strip())


def _build_llm_client() -> AsyncOpenAI:
    """Build an OpenAI-compatible client from SYNAPSE_OPENAI_* env vars."""
    return AsyncOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("SYNAPSE_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        timeout=float(os.environ.get("SYNAPSE_OPENAI_TIMEOUT_SECONDS", "30")),
    )


def _resolve_llm_model(default: str) -> str:
    return os.environ.get("SYNAPSE_OPENAI_MODEL") or default


def _user_authorized_dispatch(user_text: str, phrases: tuple[str, ...]) -> bool:
    """Return True iff the user's last utterance is one of the trigger phrases."""
    cleaned = user_text.strip().rstrip("。.！!，,").lower()
    if cleaned in phrases:
        return True
    # Tolerate a short leading prefix (e.g. "好的，确认执行") but require the phrase to dominate.
    for phrase in phrases:
        if cleaned.endswith(phrase) and len(cleaned) <= len(phrase) + 8:
            return True
    return False


async def _summarize_conversation_to_task(
    *,
    history: list[dict[str, Any]],
    llm_client: AsyncOpenAI,
    llm_model: str,
) -> str:
    """Compress the chat history into a single self-contained task description for the executor."""
    summary_messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You extract a task spec from a voice conversation between a user and "
                "their planning assistant. Output ONLY the spec — no preface or sign-off. "
                "Format:\n"
                "1. Line 1: one-sentence title\n"
                "2. Blank line\n"
                "3. Detailed description: what to build, why, in/out of scope\n"
                "4. Acceptance criteria (if mentioned)\n"
                "Use the user's language. Be self-contained — the executor sees only this text."
            ),
        }
    ]
    for m in history:
        if m.get("role") not in ("user", "assistant"):
            continue
        content = _extract_message_text(m.get("content")) or ""
        if not content:
            continue
        summary_messages.append({"role": m["role"], "content": content})
    summary_messages.append({
        "role": "user",
        "content": "Output the final task spec for the executor based on the conversation above.",
    })
    completion = await llm_client.chat.completions.create(
        model=llm_model,
        messages=summary_messages,
        temperature=0.2,
        max_tokens=600,
    )
    return (completion.choices[0].message.content or "").strip()


async def _dispatch_task_to_executor(
    *,
    transport: HttpNewbroConnectorTransport,
    synapse_session_id: str,
    task_text: str,
    target_persona_id: str | None,
) -> bool:
    """Submit the agreed task as a draft and immediately send it to the executor.

    The draft pipeline binds the resulting task to a specific bro (persona) via
    `assigned_bro_id`. Without that binding the task lands in `waiting_executor`
    forever because no executor node will pick it up. When the caller does not
    supply a target_persona_id, fall back to the first runtime persona on the
    session.
    """
    # Use a longer timeout than the connector default — the asr-turns endpoint
    # internally calls the LLM-driven draft rewriter, which can take 5–30s.
    timeout = max(transport.request_timeout_seconds, 120.0)
    async with httpx.AsyncClient(
        base_url=transport.base_url, timeout=timeout, trust_env=False,
    ) as client:
        resolved_persona_id = target_persona_id
        if not resolved_persona_id:
            try:
                personas_resp = await client.get(
                    f"{API_PREFIX}/sessions/{synapse_session_id}/personas"
                )
                if personas_resp.status_code == 200:
                    for p in personas_resp.json() or []:
                        pid = p.get("persona_id") or p.get("id")
                        if pid:
                            resolved_persona_id = pid
                            _logger.info(
                                "[convoai.dispatch] auto-bound to persona %s (%s)",
                                pid, p.get("name"),
                            )
                            break
            except Exception:
                _logger.exception("[convoai.dispatch] failed to fetch session personas")

        if not resolved_persona_id:
            _logger.error(
                "[convoai.dispatch] no persona available on session %s — "
                "task would stay in waiting_executor",
                synapse_session_id,
            )
            return False

        r1 = await client.post(
            f"{API_PREFIX}/sessions/{synapse_session_id}/draft/asr-turns",
            json={"raw_text": task_text, "assigned_bro_id": resolved_persona_id},
        )
        if r1.status_code >= 400:
            _logger.error("[convoai.dispatch] asr-turns failed %s: %s", r1.status_code, r1.text[:200])
            return False
        draft_session_id = r1.json().get("id")
        if not draft_session_id:
            _logger.error("[convoai.dispatch] draft submit returned no id")
            return False
        r2 = await client.post(
            f"{API_PREFIX}/sessions/{synapse_session_id}/draft/send",
            json={"draft_session_id": draft_session_id},
        )
        if r2.status_code >= 400:
            _logger.error("[convoai.dispatch] draft/send failed %s: %s", r2.status_code, r2.text[:200])
            return False
        _logger.info(
            "[convoai.dispatch] task dispatched (persona=%s): %s",
            resolved_persona_id, r2.json(),
        )
        return True


class AgoraConvoAIConnectorModule(BaseConnectorModule):
    slug = "agora-convoai"

    def __init__(self, settings: AgoraConvoAIConnectorSettings | None = None) -> None:
        self._settings = settings or load_agora_connector_settings()

    def build_router(self) -> APIRouter:
        settings = self._settings
        transport = HttpNewbroConnectorTransport(
            settings.synapse_base_url,
            request_timeout_seconds=settings.request_timeout_seconds,
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

        @router.get("/voice-transcripts/{session_id}")
        async def voice_transcripts(session_id: str, since: float = 0.0) -> dict[str, object]:
            """Backend-side transcript log for the live voice call.

            Polled by the frontend while a call is active. The chat_completions
            bridge records every user input + agent reply here, so the UI can
            show subtitles without depending on Agora's RTM/datastream channel
            (which is unreliable on some networks). Only populated when
            `conversation_brain_prompt` is configured — empty list otherwise.

            Returns turns with `ts > since` (use the largest ts you've seen as
            the next cursor) and the latest_ts in the store.
            """
            bucket = _VOICE_TRANSCRIPTS.get(session_id, [])
            new_items = [t for t in bucket if float(t.get("ts", 0)) > since]
            latest_ts = max((float(t.get("ts", 0)) for t in bucket), default=0.0)
            return {
                "turns": new_items,
                "latest_ts": latest_ts,
                "enabled": _conversation_brain_enabled(settings),
            }

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

            # ── Legacy path: forward STT into the draft pipeline and ack with
            # "Draft updated.". Used unless the operator opts into the new
            # conversation-brain mode by setting `conversation_brain_prompt`.
            if not _conversation_brain_enabled(settings):
                if payload.stream:
                    return StreamingResponse(
                        _legacy_stream_completion(
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

            # ── Conversation-brain mode: real LLM proxy + dispatch trigger.
            _push_voice_transcript(binding.synapse_session_id, "user", user_text)

            llm_model = _resolve_llm_model(payload.model or AGORA_BRIDGE_MODEL)
            client = _build_llm_client()
            phrases = _dispatch_trigger_phrases(settings)

            # Dispatch trigger MUST run before the stream branch: Agora calls
            # this endpoint with stream=true by convention, so a stream-only
            # check would never fire. We always return a single short reply
            # when dispatching, whether the caller asked for streaming or not.
            if _user_authorized_dispatch(user_text, phrases):
                _logger.info("[convoai.bridge] dispatch trigger fired user=%r", user_text)
                try:
                    task_text = await _summarize_conversation_to_task(
                        history=payload.messages,
                        llm_client=client,
                        llm_model=llm_model,
                    )
                    if not task_text:
                        raise RuntimeError("Empty task summary from LLM.")
                    dispatched = await _dispatch_task_to_executor(
                        transport=transport,
                        synapse_session_id=binding.synapse_session_id,
                        task_text=task_text,
                        target_persona_id=target_persona_id,
                    )
                except Exception as exc:
                    _logger.exception("[convoai.bridge] dispatch flow failed")
                    err_reply = (
                        f"Sorry, I hit an error while dispatching the task: {exc}. "
                        "Could we re-confirm the requirement?"
                    )
                    _push_voice_transcript(binding.synapse_session_id, "agent", err_reply)
                    return _completion_or_stream_response(
                        stream=payload.stream,
                        completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                        created=int(time.time()),
                        model_name=llm_model,
                        reply_text=err_reply,
                    )
                if dispatched:
                    confirm_reply = (
                        "Got it. I have handed the task off to the executor. "
                        "I'll stay on the line for follow-ups."
                    )
                    _logger.info("[convoai.bridge] dispatched task: %s", task_text[:200])
                else:
                    confirm_reply = (
                        "The backend rejected the dispatch. Let's re-check the "
                        "requirement and try again."
                    )
                    _logger.error("[convoai.bridge] dispatch rejected by backend")
                _push_voice_transcript(binding.synapse_session_id, "agent", confirm_reply)
                return _completion_or_stream_response(
                    stream=payload.stream,
                    completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                    created=int(time.time()),
                    model_name=llm_model,
                    reply_text=confirm_reply,
                )

            sanitized_messages = _sanitize_chat_history(
                payload.messages,
                system_prompt=_conversation_brain_prompt(settings),
            )
            if payload.stream:
                return StreamingResponse(
                    _stream_brain_completion(
                        synapse_session_id=binding.synapse_session_id,
                        sanitized_messages=sanitized_messages,
                        llm_model=llm_model,
                        llm_client=client,
                    ),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            try:
                completion = await client.chat.completions.create(
                    model=llm_model,
                    messages=sanitized_messages,
                    temperature=0.6,
                    max_tokens=400,
                )
                reply_text = (completion.choices[0].message.content or "").strip() or "..."
                _push_voice_transcript(binding.synapse_session_id, "agent", reply_text)
                return JSONResponse(
                    _build_completion_response(
                        completion_id=f"chatcmpl-{uuid4().hex[:8]}",
                        created=int(time.time()),
                        model_name=llm_model,
                        reply_text=reply_text,
                    )
                )
            except Exception as exc:
                _logger.exception("[convoai.bridge] LLM call failed")
                raise HTTPException(status_code=502, detail=f"LLM upstream error: {exc}") from exc

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


def _completion_or_stream_response(
    *,
    stream: bool,
    completion_id: str,
    created: int,
    model_name: str,
    reply_text: str,
):
    """Return reply_text either as a single JSON completion or as a 3-chunk SSE stream.

    Used by the dispatch-trigger path which fires for both stream and non-stream
    requests but always has a single short reply (no need to actually stream).
    """
    if not stream:
        return JSONResponse(
            _build_completion_response(
                completion_id=completion_id,
                created=created,
                model_name=model_name,
                reply_text=reply_text,
            )
        )

    async def _gen() -> AsyncIterator[str]:
        yield _sse_payload(
            _build_stream_chunk(
                completion_id=completion_id,
                created=created,
                model_name=model_name,
                delta={"role": "assistant", "content": reply_text},
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

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _legacy_stream_completion(
    *,
    transport: HttpNewbroConnectorTransport,
    synapse_session_id: str,
    user_text: str,
    model_name: str,
    target_persona_id: str | None = None,
) -> AsyncIterator[str]:
    """Legacy "Draft updated." stream — forward STT into the draft pipeline and ack."""
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


def _sanitize_chat_history(
    messages: list[dict[str, Any]],
    *,
    system_prompt: str,
) -> list[dict[str, str]]:
    """Build a clean OpenAI-style message list with our system prompt prepended.

    Drops messages that don't have a role we recognise or whose content is empty
    after extraction. Forces our own system prompt at the front and skips any
    system messages forwarded by the agent runtime so the final prompt stays
    deterministic.
    """
    sanitized: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = _extract_message_text(m.get("content")) or ""
        if not content:
            continue
        sanitized.append({"role": role, "content": content})
    return sanitized


async def _stream_brain_completion(
    *,
    synapse_session_id: str,
    sanitized_messages: list[dict[str, str]],
    llm_model: str,
    llm_client: AsyncOpenAI,
) -> AsyncIterator[str]:
    """Stream the conversation-brain LLM response back as OpenAI-compatible SSE."""
    completion_id = f"chatcmpl-{uuid4().hex[:8]}"
    created = int(time.time())
    yield _sse_payload(
        _build_stream_chunk(
            completion_id=completion_id,
            created=created,
            model_name=llm_model,
            delta={"role": "assistant", "content": ""},
        )
    )
    accumulated = ""
    try:
        stream = await llm_client.chat.completions.create(
            model=llm_model,
            messages=sanitized_messages,
            temperature=0.6,
            max_tokens=400,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = delta.content if delta and delta.content else None
            if piece:
                accumulated += piece
                yield _sse_payload(
                    _build_stream_chunk(
                        completion_id=completion_id,
                        created=created,
                        model_name=llm_model,
                        delta={"content": piece},
                    )
                )
        yield _sse_payload(
            _build_stream_chunk(
                completion_id=completion_id,
                created=created,
                model_name=llm_model,
                delta={},
                finish_reason="stop",
            )
        )
        yield "data: [DONE]\n\n"
        if accumulated.strip():
            _push_voice_transcript(synapse_session_id, "agent", accumulated)
    except Exception as exc:
        _logger.exception("[convoai.bridge] streaming LLM call failed")
        raise HTTPException(status_code=502, detail=f"LLM upstream error: {exc}") from exc

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
