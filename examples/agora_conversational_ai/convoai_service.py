from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import httpx

from .models import FrontendSessionDiagnostics
from .settings import AgoraBridgeSettings
from .token_utils import build_token_with_rtm


class ConvoAIConfigurationError(RuntimeError):
    pass


class ConvoAIRuntimeError(RuntimeError):
    pass


@dataclass(slots=True)
class PreparedConvoAISession:
    prepared_session_id: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    user_rtm_uid: str
    agent_uid: str
    agent_rtm_uid: str
    enable_string_uid: bool
    profile: str | None = None
    display_name: str | None = None
    diagnostics: FrontendSessionDiagnostics | None = None


@dataclass(slots=True)
class ActivatedConvoAISession:
    prepared_session_id: str
    runtime_agent_id: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    user_rtm_uid: str
    agent_uid: str
    agent_rtm_uid: str
    enable_string_uid: bool
    profile: str | None = None
    display_name: str | None = None
    diagnostics: FrontendSessionDiagnostics | None = None


@dataclass(slots=True)
class _PreparedLocalState:
    bootstrap: PreparedConvoAISession
    client: object
    agent: object


@dataclass(slots=True)
class _LocalConvoAIHandle:
    bootstrap: ActivatedConvoAISession
    client: object
    session: object


class ConvoAIService(Protocol):
    async def prepare_session(
        self,
        *,
        profile: str,
        channel_name: str,
        display_name: str | None,
        user_id: str | None,
    ) -> PreparedConvoAISession:
        ...

    async def activate_session(
        self,
        prepared_session_id: str,
        *,
        chat_completions_url: str,
    ) -> ActivatedConvoAISession:
        ...

    async def stop_session(self, runtime_agent_id: str) -> None:
        ...

    async def speak(self, runtime_agent_id: str, text: str) -> None:
        ...


def _require(value: str | int | None, name: str) -> str | int:
    if value in (None, ""):
        raise ConvoAIConfigurationError(f"Missing required setting: {name}")
    return value


def _parse_numeric_uid(value: str | None, fallback: int) -> int:
    if value is None or not value.strip():
        return fallback
    try:
        return int(value)
    except ValueError as exc:
        raise ConvoAIConfigurationError("user_id must be numeric for RTC join.") from exc


class AgoraSDKConvoAIService:
    def __init__(self, settings: AgoraBridgeSettings) -> None:
        self._settings = settings
        self._prepared_sessions: dict[str, _PreparedLocalState] = {}
        self._sessions: dict[str, _LocalConvoAIHandle] = {}

    async def prepare_session(
        self,
        *,
        profile: str,
        channel_name: str,
        display_name: str | None,
        user_id: str | None,
    ) -> PreparedConvoAISession:
        app_id = str(_require(self._settings.default_app_id, "AGORA_APP_ID"))
        app_certificate = str(
            _require(self._settings.app_certificate, "AGORA_APP_CERTIFICATE")
        )
        deepgram_api_key = str(_require(self._settings.deepgram_api_key, "DEEPGRAM_API_KEY"))
        elevenlabs_api_key = str(
            _require(self._settings.elevenlabs_api_key, "ELEVENLABS_API_KEY")
        )
        elevenlabs_voice_id = str(
            _require(self._settings.elevenlabs_voice_id, "ELEVENLABS_VOICE_ID")
        )

        (
            AsyncAgora,
            Area,
            Agent,
            _AsyncAgentSession,
            DeepgramSTT,
            _OpenAI,
            ElevenLabsTTS,
            AdvancedFeatures,
            SessionParams,
        ) = self._load_sdk_types()

        channel = channel_name.strip() if channel_name.strip() else f"synapse-{uuid4().hex[:8]}"
        user_uid = _parse_numeric_uid(user_id, self._settings.user_uid)
        user_rtm_uid = f"{user_uid}-{channel}"
        agent_uid = str(self._settings.agent_uid)
        agent_rtm_uid = f"{agent_uid}-{channel}"

        client_token = build_token_with_rtm(
            channel_name=channel,
            rtc_uid=user_uid,
            app_id=app_id,
            app_certificate=app_certificate,
            rtm_uid=user_rtm_uid,
            token_expire=self._settings.client_token_ttl_seconds,
        )

        try:
            area = getattr(Area, self._settings.convoai_area)
        except AttributeError as exc:
            raise ConvoAIConfigurationError(
                f"Unsupported AGORA_CONVOAI_AREA: {self._settings.convoai_area}"
            ) from exc

        client = AsyncAgora(
            area=area,
            app_id=app_id,
            app_certificate=app_certificate,
            debug=self._settings.sdk_debug,
        )
        await client.select_best_domain()

        agent = Agent(
            name=f"synapse_agent_{uuid4().hex[:8]}",
            instructions=self._settings.agent_instructions,
            greeting=self._settings.agent_greeting,
            advanced_features=AdvancedFeatures(enable_rtm=True),
            parameters=SessionParams(
                data_channel="rtm",
                enable_metrics=True,
                enable_error_message=True,
                transcript={
                    "enable": True,
                    "protocol_version": "v2",
                    "enable_words": False,
                },
                enable_dump=True,
            ),
        )
        agent = agent.with_stt(
            DeepgramSTT(
                api_key=deepgram_api_key,
                language=self._settings.deepgram_language,
            )
        )
        agent = agent.with_tts(
            ElevenLabsTTS(
                key=elevenlabs_api_key,
                voice_id=elevenlabs_voice_id,
                model_id=self._settings.elevenlabs_model_id,
                sample_rate=self._settings.elevenlabs_sample_rate,
            )
        )

        prepared_session_id = f"prepared-{uuid4().hex[:8]}"
        diagnostics = FrontendSessionDiagnostics(
            convoai_area=self._settings.convoai_area,
            selected_url=client.get_current_url(),
            runtime_agent_id=None,
            agent_uid=agent_uid,
            agent_rtm_uid=agent_rtm_uid,
            rtc_uid=user_uid,
            rtm_user_id=user_rtm_uid,
            enable_string_uid=False,
            enable_rtm=True,
            data_channel="rtm",
            enable_metrics=True,
            enable_error_message=True,
        )
        bootstrap = PreparedConvoAISession(
            prepared_session_id=prepared_session_id,
            app_id=app_id,
            channel_name=channel,
            token=client_token.token,
            uid=user_uid,
            user_rtm_uid=user_rtm_uid,
            agent_uid=agent_uid,
            agent_rtm_uid=agent_rtm_uid,
            enable_string_uid=False,
            profile=profile,
            display_name=display_name,
            diagnostics=diagnostics,
        )
        self._prepared_sessions[prepared_session_id] = _PreparedLocalState(
            bootstrap=bootstrap,
            client=client,
            agent=agent,
        )
        return bootstrap

    async def activate_session(
        self,
        prepared_session_id: str,
        *,
        chat_completions_url: str,
    ) -> ActivatedConvoAISession:
        try:
            state = self._prepared_sessions.pop(prepared_session_id)
        except KeyError as exc:
            raise KeyError(f"Unknown prepared session id: {prepared_session_id}") from exc

        bootstrap = state.bootstrap
        AsyncAgentSession = self._load_sdk_types()[3]
        OpenAI = self._load_sdk_types()[5]
        agent = state.agent.with_llm(
            OpenAI(
                base_url=chat_completions_url,
                model=self._settings.default_model,
            )
        )
        session = AsyncAgentSession(
            client=state.client,
            agent=agent,
            app_id=bootstrap.app_id,
            app_certificate=str(_require(self._settings.app_certificate, "AGORA_APP_CERTIFICATE")),
            name=f"synapse_agent_{uuid4().hex[:8]}",
            channel=bootstrap.channel_name,
            agent_uid=bootstrap.agent_uid,
            remote_uids=["*"],
            enable_string_uid=False,
            expires_in=self._settings.client_token_ttl_seconds,
            debug=self._settings.sdk_debug,
        )

        try:
            runtime_agent_id = await session.start()
        except httpx.ConnectError as exc:
            raise ConvoAIRuntimeError(
                "Failed to reach Agora ConvoAI endpoint "
                f"{state.client.get_current_url()} for area {self._settings.convoai_area}. "
                "Check network access or try another AGORA_CONVOAI_AREA."
            ) from exc

        runtime_agent_id = str(runtime_agent_id)
        diagnostics = FrontendSessionDiagnostics(
            convoai_area=self._settings.convoai_area,
            selected_url=state.client.get_current_url(),
            runtime_agent_id=runtime_agent_id,
            agent_uid=bootstrap.agent_uid,
            agent_rtm_uid=bootstrap.agent_rtm_uid,
            rtc_uid=bootstrap.uid,
            rtm_user_id=bootstrap.user_rtm_uid,
            enable_string_uid=False,
            enable_rtm=True,
            data_channel="rtm",
            enable_metrics=True,
            enable_error_message=True,
        )
        activated = ActivatedConvoAISession(
            prepared_session_id=bootstrap.prepared_session_id,
            runtime_agent_id=runtime_agent_id,
            app_id=bootstrap.app_id,
            channel_name=bootstrap.channel_name,
            token=bootstrap.token,
            uid=bootstrap.uid,
            user_rtm_uid=bootstrap.user_rtm_uid,
            agent_uid=bootstrap.agent_uid,
            agent_rtm_uid=bootstrap.agent_rtm_uid,
            enable_string_uid=False,
            profile=bootstrap.profile,
            display_name=bootstrap.display_name,
            diagnostics=diagnostics,
        )
        self._sessions[runtime_agent_id] = _LocalConvoAIHandle(
            bootstrap=activated,
            client=state.client,
            session=session,
        )
        return activated

    async def stop_session(self, runtime_agent_id: str) -> None:
        handle = self._sessions.pop(runtime_agent_id, None)
        if handle is None:
            raise KeyError(f"Unknown runtime agent id: {runtime_agent_id}")
        await handle.session.stop()

    async def speak(self, runtime_agent_id: str, text: str) -> None:
        handle = self._sessions.get(runtime_agent_id)
        if handle is None:
            raise KeyError(f"Unknown runtime agent id: {runtime_agent_id}")
        await handle.session.say(
            text,
            priority=self._settings.speak_priority,
            interruptable=self._settings.speak_interruptable,
        )

    def _load_sdk_types(self):
        try:
            from agora_agent import Agent, Area, AsyncAgentSession, AsyncAgora
            from agora_agent.agentkit import (
                AdvancedFeatures,
                DeepgramSTT,
                ElevenLabsTTS,
                OpenAI,
                SessionParams,
            )
        except ImportError as exc:
            raise ConvoAIConfigurationError(
                "Missing Agora Python SDK. Install `agora-agent-server-sdk` to run this example backend."
            ) from exc
        return (
            AsyncAgora,
            Area,
            Agent,
            AsyncAgentSession,
            DeepgramSTT,
            OpenAI,
            ElevenLabsTTS,
            AdvancedFeatures,
            SessionParams,
        )
