from __future__ import annotations

from dataclasses import dataclass

import pytest

from synapse.connectors.base import ConnectorBindingRegistry
from synapse.connectors.voice.agora_convoai.models import ConnectorSessionDiagnostics, ConnectorSessionPrepareRequest
from synapse.connectors.voice.agora_convoai.service import PreparedConvoAISession
from synapse.connectors.voice.agora_convoai.session_service import AgoraConnectorSessionService
from synapse.connectors.voice.agora_convoai.settings import AgoraConvoAIConnectorSettings


@dataclass
class _FakeTransport:
    async def create_session(self) -> str:
        return "session-1"

    async def watch_notification_texts(self, session_id: str):
        if False:
            yield session_id


@dataclass
class _FakeSpeaker:
    async def speak(self, runtime_session_id: str, text: str) -> None:
        return None


class _CapturingConvoAIService:
    def __init__(self) -> None:
        self.last_prepare: dict[str, object] | None = None

    async def prepare_session(self, **kwargs) -> PreparedConvoAISession:
        self.last_prepare = kwargs
        return PreparedConvoAISession(
            prepared_session_id="prepared-1",
            app_id="agora-app",
            channel_name=str(kwargs["channel_name"]),
            token="token",
            uid=int(kwargs["user_uid"] or 101),
            user_rtm_uid="101-room",
            agent_uid=str(kwargs["agent_uid"]),
            agent_rtm_uid="9001-room",
            enable_string_uid=False,
            profile=str(kwargs["profile"]),
            display_name=kwargs["display_name"],
            diagnostics=ConnectorSessionDiagnostics(
                convoai_area="US",
                selected_url="https://fake-convoai.local/api",
                runtime_session_id=None,
                asr_vendor="deepgram",
                asr_credential_mode="managed",
                asr_model="nova-3",
                tts_vendor="minimax",
                tts_credential_mode="managed",
                tts_model="speech_2_6_turbo",
                agent_uid=str(kwargs["agent_uid"]),
                agent_rtm_uid="9001-room",
                rtc_uid=int(kwargs["user_uid"] or 101),
                rtm_user_id="101-room",
                enable_string_uid=False,
                enable_rtm=True,
                data_channel="rtm",
                enable_metrics=True,
                enable_error_message=True,
            ),
        )

    async def activate_session(self, prepared_session_id: str, *, chat_completions_url: str):
        raise NotImplementedError

    async def stop_session(self, runtime_session_id: str) -> None:
        return None

    async def speak(self, runtime_session_id: str, text: str) -> None:
        return None


@pytest.mark.anyio
async def test_prepare_session_preserves_empty_string_instruction_overrides():
    service = _CapturingConvoAIService()
    session_service = AgoraConnectorSessionService(
        ConnectorBindingRegistry(_FakeTransport(), _FakeSpeaker()),
        AgoraConvoAIConnectorSettings(
            app_id="agora-app",
            app_certificate="cert",
            agent_instructions="default instructions",
            agent_greeting="default greeting",
        ),
        convoai_service=service,
    )

    await session_service.prepare_session(
        ConnectorSessionPrepareRequest(
            channel_name="demo-room",
            agent_instructions="",
            agent_greeting="",
        )
    )

    assert service.last_prepare is not None
    assert service.last_prepare["agent_instructions"] == ""
    assert service.last_prepare["agent_greeting"] == ""
