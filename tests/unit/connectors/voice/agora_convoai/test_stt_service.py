import re
import json

import pytest
import httpx

from synapse.connectors.voice.agora_convoai.models import (
    SttSessionHeartbeatRequest,
    SttSessionLeaveRequest,
    SttSessionPrepareRequest,
    SttSessionStartRequest,
)
from synapse.connectors.voice.agora_convoai.settings import AgoraConvoAIConnectorSettings
from synapse.connectors.voice.agora_convoai.stt_service import AgoraSttService, _redact_stt_join_payload


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_redact_stt_join_payload_keeps_diagnostics_without_tokens():
    payload = {
        "name": "nbstt-task-1",
        "languages": ["zh-CN", "en-US"],
        "maxIdleTime": 60,
        "rtcConfig": {
            "channelName": "nbstt-channel",
            "pubBotUid": "100101",
            "pubBotToken": "pub-secret-token",
            "subBotUid": "100102",
            "subBotToken": "sub-secret-token",
            "subscribeAudioUids": ["101"],
        },
    }

    redacted = _redact_stt_join_payload(payload)
    serialized = json.dumps(redacted)

    assert "pub-secret-token" not in serialized
    assert "sub-secret-token" not in serialized
    assert redacted["languages"] == ["zh-CN", "en-US"]
    assert redacted["rtcConfig"]["channelName"] == "nbstt-channel"
    assert redacted["rtcConfig"]["pubBotUid"] == "100101"
    assert redacted["rtcConfig"]["pubBotToken"] == "<redacted>"
    assert redacted["rtcConfig"]["subBotUid"] == "100102"
    assert redacted["rtcConfig"]["subBotToken"] == "<redacted>"
    assert redacted["rtcConfig"]["subscribeAudioUids"] == ["101"]


def test_stt_prepare_returns_unique_browser_join_credentials_without_joining_agora(monkeypatch):
    calls = []

    async def fake_post(self, url, *, headers=None, json=None):
        calls.append((url, headers, json))
        return httpx.Response(200, json={"agent_id": "agent-1", "status": "started"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = AgoraSttService(
        AgoraConvoAIConnectorSettings(
            app_id="app-id",
            app_certificate="app-cert",
        )
    )

    first = service.prepare_session(
        SttSessionPrepareRequest(
            synapse_session_id="session with spaces 中文",
            assigned_bro_id="bro/1?x=y",
            user_uid=101,
        )
    )
    second = service.prepare_session(
        SttSessionPrepareRequest(
            synapse_session_id="session with spaces 中文",
            assigned_bro_id="bro/1?x=y",
            user_uid=101,
        )
    )

    assert first.app_id == "app-id"
    assert first.uid == 101
    assert first.token.startswith("007")
    assert first.status == "prepared"
    assert first.channel_name != second.channel_name
    assert len(first.channel_name) <= 64
    assert re.fullmatch(r"[A-Za-z0-9_-]+", first.channel_name)
    assert calls == []


@pytest.mark.anyio
async def test_stt_start_uses_prepared_channel_and_agora_token_auth(monkeypatch):
    calls = []

    async def fake_post(self, url, *, headers=None, json=None):
        calls.append((url, headers, json))
        return httpx.Response(200, json={"agent_id": "agent-1", "status": "started"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = AgoraSttService(
        AgoraConvoAIConnectorSettings(
            app_id="app-id",
            app_certificate="app-cert",
        )
    )
    prepared = service.prepare_session(
        SttSessionPrepareRequest(
            synapse_session_id="session-1",
            assigned_bro_id="bro-1",
            user_uid=101,
        )
    )

    response = await service.start_session(
        SttSessionStartRequest(
            prepared_stt_session_id=prepared.prepared_stt_session_id,
        )
    )

    assert response.agent_id == "agent-1"
    assert response.channel_name == prepared.channel_name
    assert response.token == prepared.token
    assert calls
    url, headers, payload = calls[0]
    assert url == "https://api.agora.io/api/speech-to-text/v1/projects/app-id/join"
    assert headers["Authorization"].startswith("agora token=007")
    assert "Basic" not in headers["Authorization"]
    assert payload["name"].startswith("nbstt-task-")
    assert payload["languages"] == ["zh-CN", "en-US"]
    assert response.languages == ["zh-CN", "en-US"]
    assert response.subscribe_audio_uids == [str(prepared.uid)]
    assert len(payload["name"]) <= 64
    assert re.fullmatch(r"[A-Za-z0-9_-]+", payload["name"])
    assert payload["rtcConfig"]["channelName"] == prepared.channel_name
    assert "enableJsonProtocol" not in payload["rtcConfig"]
    assert payload["rtcConfig"]["subscribeAudioUids"] == [str(prepared.uid)]
    assert payload["rtcConfig"]["pubBotUid"] == str(response.pub_bot_uid)
    assert payload["rtcConfig"]["subBotUid"] == str(response.sub_bot_uid)
    assert payload["rtcConfig"]["subBotToken"].startswith("007")
    assert response.uid != response.pub_bot_uid
    assert response.uid != response.sub_bot_uid
    assert response.pub_bot_uid != response.sub_bot_uid
    assert payload["rtcConfig"]["pubBotToken"].startswith("007")


@pytest.mark.anyio
async def test_stt_start_uses_unique_task_names_to_avoid_agora_conflicts(monkeypatch):
    calls = []

    async def fake_post(self, url, *, headers=None, json=None):
        calls.append((url, headers, json))
        return httpx.Response(200, json={"agent_id": f"agent-{len(calls)}", "status": "started"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = AgoraSttService(
        AgoraConvoAIConnectorSettings(app_id="app-id", app_certificate="app-cert")
    )
    first = service.prepare_session(
        SttSessionPrepareRequest(synapse_session_id="session-1", assigned_bro_id="bro-1")
    )
    second = service.prepare_session(
        SttSessionPrepareRequest(synapse_session_id="session-1", assigned_bro_id="bro-1")
    )

    await service.start_session(SttSessionStartRequest(prepared_stt_session_id=first.prepared_stt_session_id))
    await service.start_session(SttSessionStartRequest(prepared_stt_session_id=second.prepared_stt_session_id))

    first_name = calls[0][2]["name"]
    second_name = calls[1][2]["name"]
    assert first_name != second_name
    assert first_name.startswith("nbstt-task-")
    assert second_name.startswith("nbstt-task-")


@pytest.mark.anyio
async def test_stt_leave_stops_active_session(monkeypatch):
    calls = []

    async def fake_post(self, url, *, headers=None, json=None):
        calls.append((url, headers, json))
        if url.endswith("/join"):
            return httpx.Response(200, json={"agent_id": "agent-1", "status": "started"})
        return httpx.Response(200, json={"status": "stopped"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = AgoraSttService(
        AgoraConvoAIConnectorSettings(app_id="app-id", app_certificate="app-cert")
    )
    prepared = service.prepare_session(
        SttSessionPrepareRequest(synapse_session_id="session-1", assigned_bro_id="bro-1")
    )
    started = await service.start_session(
        SttSessionStartRequest(prepared_stt_session_id=prepared.prepared_stt_session_id)
    )

    await service.leave_session(SttSessionLeaveRequest(stt_session_id=started.stt_session_id))

    assert calls[-1][0] == "https://api.agora.io/api/speech-to-text/v1/projects/app-id/agents/agent-1/leave"
    with pytest.raises(KeyError):
        service.heartbeat_session(SttSessionHeartbeatRequest(stt_session_id=started.stt_session_id))


@pytest.mark.anyio
async def test_stt_heartbeat_timeout_directly_stops_active_session(monkeypatch):
    clock = _Clock()
    calls = []

    async def fake_post(self, url, *, headers=None, json=None):
        calls.append(url)
        if url.endswith("/join"):
            return httpx.Response(200, json={"agent_id": "agent-1", "status": "started"})
        return httpx.Response(200, json={"status": "stopped"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = AgoraSttService(
        AgoraConvoAIConnectorSettings(app_id="app-id", app_certificate="app-cert"),
        now=clock,
    )
    prepared = service.prepare_session(
        SttSessionPrepareRequest(synapse_session_id="session-1", assigned_bro_id="bro-1")
    )
    started = await service.start_session(
        SttSessionStartRequest(prepared_stt_session_id=prepared.prepared_stt_session_id)
    )

    clock.advance(30)
    service.heartbeat_session(SttSessionHeartbeatRequest(stt_session_id=started.stt_session_id))
    clock.advance(61)
    await service.sweep_expired_sessions()

    assert calls[-1] == "https://api.agora.io/api/speech-to-text/v1/projects/app-id/agents/agent-1/leave"
    with pytest.raises(KeyError):
        await service.stop_session(started.stt_session_id)


@pytest.mark.anyio
async def test_stt_leave_cleans_prepared_only_session(monkeypatch):
    calls = []

    async def fake_post(self, url, *, headers=None, json=None):
        calls.append(url)
        return httpx.Response(200, json={"agent_id": "agent-1", "status": "started"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    service = AgoraSttService(
        AgoraConvoAIConnectorSettings(app_id="app-id", app_certificate="app-cert")
    )
    prepared = service.prepare_session(
        SttSessionPrepareRequest(synapse_session_id="session-1", assigned_bro_id="bro-1")
    )

    await service.leave_session(
        SttSessionLeaveRequest(prepared_stt_session_id=prepared.prepared_stt_session_id)
    )

    assert calls == []
    with pytest.raises(KeyError):
        await service.start_session(
            SttSessionStartRequest(prepared_stt_session_id=prepared.prepared_stt_session_id)
        )
