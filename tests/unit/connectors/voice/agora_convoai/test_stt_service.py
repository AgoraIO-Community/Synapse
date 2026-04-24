import pytest
import httpx

from synapse.connectors.voice.agora_convoai.models import SttSessionPrepareRequest, SttSessionStartRequest
from synapse.connectors.voice.agora_convoai.settings import AgoraConvoAIConnectorSettings
from synapse.connectors.voice.agora_convoai.stt_service import AgoraSttService


def test_stt_prepare_returns_browser_join_credentials():
    service = AgoraSttService(
        AgoraConvoAIConnectorSettings(
            app_id="app-id",
            app_certificate="app-cert",
        )
    )

    response = service.prepare_session(
        SttSessionPrepareRequest(
            synapse_session_id="session-1",
            user_uid=101,
        )
    )

    assert response.app_id == "app-id"
    assert response.channel_name == "session-1"
    assert response.uid == 101
    assert response.token.startswith("007")


@pytest.mark.anyio
async def test_stt_join_uses_agora_token_auth(monkeypatch):
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

    response = await service.start_session(
        SttSessionStartRequest(
            synapse_session_id="session-1",
            assigned_bro_id="bro-1",
            user_uid=101,
        )
    )

    assert response.agent_id == "agent-1"
    assert calls
    url, headers, payload = calls[0]
    assert url == "https://api.agora.io/api/speech-to-text/v1/projects/app-id/join"
    assert headers["Authorization"].startswith("agora token=007")
    assert "Basic" not in headers["Authorization"]
    assert payload["name"] == "newbro-stt-session-1-bro-1"
    assert payload["rtcConfig"]["enableJsonProtocol"] is True
    assert payload["rtcConfig"]["subscribeAudioUids"] == ["101"]
    assert payload["rtcConfig"]["pubBotUid"] == str(response.pub_bot_uid)
    assert payload["rtcConfig"]["subBotUid"] == str(response.sub_bot_uid)
    assert payload["rtcConfig"]["subBotToken"].startswith("007")
    assert response.uid != response.pub_bot_uid
    assert response.uid != response.sub_bot_uid
    assert response.pub_bot_uid != response.sub_bot_uid
