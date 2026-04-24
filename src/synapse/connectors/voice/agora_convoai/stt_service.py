from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import uuid4

import httpx

from .models import SttSessionPrepareRequest, SttSessionPrepareResponse, SttSessionQueryResponse, SttSessionStartRequest, SttSessionStartResponse, SttSessionStopResponse
from .service import ConvoAIConfigurationError, ConvoAIRuntimeError
from .settings import AgoraConvoAIConnectorSettings
from .token_utils import build_rtc_token


@dataclass(slots=True)
class SttSessionHandle:
    stt_session_id: str
    agent_id: str
    channel_name: str
    uid: int
    pub_bot_uid: int
    sub_bot_uid: int
    token: str
    assigned_bro_id: str
    synapse_session_id: str


class AgoraSttService:
    def __init__(self, settings: AgoraConvoAIConnectorSettings) -> None:
        self._settings = settings
        self._sessions: dict[str, SttSessionHandle] = {}
        self._http = httpx.AsyncClient(timeout=settings.request_timeout_seconds, trust_env=False)

    async def close(self) -> None:
        await self._http.aclose()

    def prepare_session(self, request: SttSessionPrepareRequest) -> SttSessionPrepareResponse:
        if not self._settings.stt.enabled:
            raise ConvoAIConfigurationError("Agora STT is disabled in connector config.")
        app_id = _require(self._settings.app_id, _app_id_requirement_name(self._settings))
        app_certificate = _require(
            self._settings.app_certificate,
            _app_certificate_requirement_name(self._settings),
        )
        channel_name = _resolve_channel_name(request.channel_name, request.synapse_session_id)
        uid = request.user_uid or self._settings.user_uid
        user_token = build_rtc_token(
            channel_name=channel_name,
            rtc_uid=uid,
            app_id=app_id,
            app_certificate=app_certificate,
            token_expire=self._settings.stt.token_ttl_seconds,
        ).token
        return SttSessionPrepareResponse(
            app_id=app_id,
            channel_name=channel_name,
            token=user_token,
            uid=uid,
        )

    async def start_session(self, request: SttSessionStartRequest) -> SttSessionStartResponse:
        if not self._settings.stt.enabled:
            raise ConvoAIConfigurationError("Agora STT is disabled in connector config.")
        app_id = _require(self._settings.app_id, _app_id_requirement_name(self._settings))
        app_certificate = _require(
            self._settings.app_certificate,
            _app_certificate_requirement_name(self._settings),
        )
        channel_name = _resolve_channel_name(request.channel_name, request.synapse_session_id)
        uid = request.user_uid or self._settings.user_uid
        pub_bot_uid = _next_bot_uid(uid, offset=100000)
        sub_bot_uid = _next_bot_uid(uid, offset=200000)
        languages = request.languages or list(self._settings.stt.languages)
        name = _build_stt_task_name(request.synapse_session_id, request.assigned_bro_id, channel_name)
        token = build_rtc_token(
            channel_name=channel_name,
            rtc_uid=pub_bot_uid,
            app_id=app_id,
            app_certificate=app_certificate,
            token_expire=self._settings.stt.token_ttl_seconds,
        ).token
        sub_bot_token = build_rtc_token(
            channel_name=channel_name,
            rtc_uid=sub_bot_uid,
            app_id=app_id,
            app_certificate=app_certificate,
            token_expire=self._settings.stt.token_ttl_seconds,
        ).token
        user_token = build_rtc_token(
            channel_name=channel_name,
            rtc_uid=uid,
            app_id=app_id,
            app_certificate=app_certificate,
            token_expire=self._settings.stt.token_ttl_seconds,
        ).token
        payload = {
            "name": name,
            "languages": languages,
            "maxIdleTime": self._settings.stt.max_idle_time,
            "rtcConfig": {
                "channelName": channel_name,
                "pubBotUid": str(pub_bot_uid),
                "pubBotToken": token,
                "subBotUid": str(sub_bot_uid),
                "subBotToken": sub_bot_token,
                "subscribeAudioUids": [str(uid)],
                "enableJsonProtocol": True,
            },
        }
        response = await self._http.post(
            f"https://api.agora.io/api/speech-to-text/v1/projects/{app_id}/join",
            headers={"Authorization": f"agora token={token}"},
            json=payload,
        )
        if response.status_code >= 400:
            raise ConvoAIRuntimeError(response.text or f"Agora STT join failed: {response.status_code}")
        body = response.json()
        agent_id = str(body.get("agent_id") or body.get("agentId") or body.get("taskId") or "")
        if not agent_id:
            raise ConvoAIRuntimeError("Agora STT join response did not include agent_id.")
        stt_session_id = f"stt-{uuid4().hex[:8]}"
        self._sessions[stt_session_id] = SttSessionHandle(
            stt_session_id=stt_session_id,
            agent_id=agent_id,
            channel_name=channel_name,
            uid=uid,
            pub_bot_uid=pub_bot_uid,
            sub_bot_uid=sub_bot_uid,
            token=token,
            assigned_bro_id=request.assigned_bro_id,
            synapse_session_id=request.synapse_session_id,
        )
        return SttSessionStartResponse(
            stt_session_id=stt_session_id,
            app_id=app_id,
            channel_name=channel_name,
            token=user_token,
            uid=uid,
            pub_bot_uid=pub_bot_uid,
            sub_bot_uid=sub_bot_uid,
            agent_id=agent_id,
            status=str(body.get("status") or "started"),
        )

    async def query_session(self, stt_session_id: str) -> SttSessionQueryResponse:
        handle = self._get_handle(stt_session_id)
        app_id = _require(self._settings.app_id, _app_id_requirement_name(self._settings))
        response = await self._http.get(
            f"https://api.agora.io/api/speech-to-text/v1/projects/{app_id}/agents/{handle.agent_id}/query",
            headers={"Authorization": f"agora token={handle.token}"},
        )
        if response.status_code >= 400:
            raise ConvoAIRuntimeError(response.text or f"Agora STT query failed: {response.status_code}")
        body = response.json()
        return SttSessionQueryResponse(
            stt_session_id=stt_session_id,
            agent_id=handle.agent_id,
            status=str(body.get("status") or "unknown"),
            raw=body,
        )

    async def stop_session(self, stt_session_id: str) -> SttSessionStopResponse:
        handle = self._get_handle(stt_session_id)
        app_id = _require(self._settings.app_id, _app_id_requirement_name(self._settings))
        response = await self._http.post(
            f"https://api.agora.io/api/speech-to-text/v1/projects/{app_id}/agents/{handle.agent_id}/leave",
            headers={"Authorization": f"agora token={handle.token}"},
        )
        self._sessions.pop(stt_session_id, None)
        if response.status_code >= 400:
            raise ConvoAIRuntimeError(response.text or f"Agora STT leave failed: {response.status_code}")
        return SttSessionStopResponse()

    def _get_handle(self, stt_session_id: str) -> SttSessionHandle:
        try:
            return self._sessions[stt_session_id]
        except KeyError as exc:
            raise KeyError("Unknown STT session.") from exc


def _next_bot_uid(user_uid: int, *, offset: int) -> int:
    return user_uid + offset if user_uid < 2147483647 - offset else user_uid - offset


def _resolve_channel_name(channel_name: str | None, synapse_session_id: str | None) -> str:
    return (channel_name or synapse_session_id or f"newbro-stt-{uuid4().hex[:8]}").strip()


def _build_stt_task_name(synapse_session_id: str, assigned_bro_id: str, fallback: str) -> str:
    raw = f"newbro-stt-{synapse_session_id}-{assigned_bro_id}"
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-_")
    if not sanitized:
        sanitized = re.sub(r"[^A-Za-z0-9_-]+", "-", f"newbro-stt-{fallback}").strip("-_")
    return (sanitized or "newbro-stt-session")[:64]


def _require(value: str | None, name: str) -> str:
    if value:
        return value
    raise ConvoAIConfigurationError(f"Missing required Agora setting: {name}")


def _app_id_requirement_name(settings: AgoraConvoAIConnectorSettings) -> str:
    return "connectors.agora-convoai.app_id" if settings.uses_yaml_config else "SYNAPSE_CONNECTOR_AGORA_CONVOAI_APP_ID"


def _app_certificate_requirement_name(settings: AgoraConvoAIConnectorSettings) -> str:
    return "connectors.agora-convoai.app_certificate" if settings.uses_yaml_config else "SYNAPSE_CONNECTOR_AGORA_CONVOAI_APP_CERTIFICATE"
