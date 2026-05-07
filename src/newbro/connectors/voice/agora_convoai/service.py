from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import httpx

from .models import ConnectorSessionDiagnostics
from .settings import AGORA_BRIDGE_MODEL, AgoraConvoAIConnectorSettings
from .token_utils import build_token_with_rtm


class ConvoAIConfigurationError(RuntimeError):
    pass


class ConvoAIRuntimeError(RuntimeError):
    pass


AGORA_CONVOAI_IMPLEMENTATION_VERSION = "agora-convoai-connector.v1"
AGORA_CONVOAI_SDK_LOADER_SIGNATURE = (
    "agora_agent:Agent",
    "agora_agent:Area",
    "agora_agent:AsyncAgentSession",
    "agora_agent:AsyncAgora",
    "agora_agent.agentkit:AdvancedFeatures",
    "agora_agent.agentkit:DeepgramSTT",
    "agora_agent.agentkit:ElevenLabsTTS",
    "agora_agent.agentkit:MiniMaxTTS",
    "agora_agent.agentkit:OpenAI",
    "agora_agent.agentkit:OpenAITTS",
    "agora_agent.agentkit:SessionParams",
)


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
    diagnostics: ConnectorSessionDiagnostics | None = None


@dataclass(slots=True)
class ActivatedConvoAISession:
    prepared_session_id: str
    runtime_session_id: str
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
    diagnostics: ConnectorSessionDiagnostics | None = None


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
        agent_instructions: str,
        agent_greeting: str,
        agent_uid: int,
        user_uid: int | None,
    ) -> PreparedConvoAISession:
        ...

    async def activate_session(
        self,
        prepared_session_id: str,
        *,
        chat_completions_url: str,
    ) -> ActivatedConvoAISession:
        ...

    async def stop_session(self, runtime_session_id: str) -> None:
        ...

    async def speak(self, runtime_session_id: str, text: str) -> None:
        ...


def _require(value: str | int | None, name: str) -> str | int:
    if value in (None, ""):
        raise ConvoAIConfigurationError(f"Missing required setting: {name}")
    return value


def _parse_numeric_uid(value: int | str | None, fallback: int) -> int:
    if value is None:
        return fallback
    raw_value = value.strip() if isinstance(value, str) else str(value)
    if not raw_value:
        return fallback
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ConvoAIConfigurationError("user_uid must be numeric for RTC join.") from exc


class AgoraSDKConvoAIService:
    def __init__(self, settings: AgoraConvoAIConnectorSettings) -> None:
        self._settings = settings
        self._prepared_sessions: dict[str, _PreparedLocalState] = {}
        self._sessions: dict[str, _LocalConvoAIHandle] = {}

    async def prepare_session(
        self,
        *,
        profile: str,
        channel_name: str,
        display_name: str | None,
        agent_instructions: str,
        agent_greeting: str,
        agent_uid: int,
        user_uid: int | None,
    ) -> PreparedConvoAISession:
        app_id = str(_require(self._settings.app_id, _app_id_requirement_name(self._settings)))
        app_certificate = str(
            _require(
                self._settings.app_certificate,
                _app_certificate_requirement_name(self._settings),
            )
        )
        (
            AsyncAgora,
            Area,
            Agent,
            _AsyncAgentSession,
            DeepgramSTT,
            _OpenAI,
            ElevenLabsTTS,
            MiniMaxTTS,
            OpenAITTS,
            AdvancedFeatures,
            SessionParams,
        ) = self._load_sdk_types()

        channel = channel_name.strip() if channel_name.strip() else f"newbro-{uuid4().hex[:8]}"
        resolved_user_uid = _parse_numeric_uid(user_uid, self._settings.user_uid)
        user_rtm_uid = f"{resolved_user_uid}-{channel}"
        resolved_agent_uid = str(agent_uid)
        agent_rtm_uid = f"{resolved_agent_uid}-{channel}"

        client_token = build_token_with_rtm(
            channel_name=channel,
            rtc_uid=resolved_user_uid,
            app_id=app_id,
            app_certificate=app_certificate,
            rtm_uid=user_rtm_uid,
            token_expire=self._settings.client_token_ttl_seconds,
        )

        try:
            area = getattr(Area, self._settings.convoai_area)
        except AttributeError as exc:
            raise ConvoAIConfigurationError(
                f"Unsupported SYNAPSE_CONNECTOR_AGORA_CONVOAI_AREA: {self._settings.convoai_area}"
            ) from exc

        client = AsyncAgora(
            area=area,
            app_id=app_id,
            app_certificate=app_certificate,
            debug=False,
        )
        await client.select_best_domain()

        agent = Agent(
            name=f"newbro_agent_{uuid4().hex[:8]}",
            instructions=agent_instructions,
            greeting=agent_greeting,
            advanced_features=AdvancedFeatures(enable_rtm=(self._settings.data_channel == "rtm")),
            parameters=SessionParams(
                data_channel=self._settings.data_channel,
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
        agent = agent.with_stt(_build_asr_vendor(self._settings, DeepgramSTT=DeepgramSTT))
        agent = agent.with_tts(
            _build_tts_vendor(
                self._settings,
                ElevenLabsTTS=ElevenLabsTTS,
                MiniMaxTTS=MiniMaxTTS,
                OpenAITTS=OpenAITTS,
            )
        )

        prepared_session_id = f"prepared-{uuid4().hex[:8]}"
        diagnostics = ConnectorSessionDiagnostics(
            convoai_area=self._settings.convoai_area,
            selected_url=client.get_current_url(),
            runtime_session_id=None,
            asr_vendor=self._settings.asr.vendor,
            asr_credential_mode=self._settings.asr.credential_mode,
            asr_model=self._settings.asr.model,
            tts_vendor=self._settings.tts.vendor,
            tts_credential_mode=self._settings.tts.credential_mode,
            tts_model=self._settings.tts.model,
            agent_uid=resolved_agent_uid,
            agent_rtm_uid=agent_rtm_uid,
            rtc_uid=resolved_user_uid,
            rtm_user_id=user_rtm_uid,
            enable_string_uid=False,
            enable_rtm=(self._settings.data_channel == "rtm"),
            data_channel=self._settings.data_channel,
            enable_metrics=True,
            enable_error_message=True,
        )
        bootstrap = PreparedConvoAISession(
            prepared_session_id=prepared_session_id,
            app_id=app_id,
            channel_name=channel,
            token=client_token.token,
            uid=resolved_user_uid,
            user_rtm_uid=user_rtm_uid,
            agent_uid=resolved_agent_uid,
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
                model=AGORA_BRIDGE_MODEL,
            )
        )
        session = AsyncAgentSession(
            client=state.client,
            agent=agent,
            app_id=bootstrap.app_id,
            app_certificate=str(
                _require(
                    self._settings.app_certificate,
                    _app_certificate_requirement_name(self._settings),
                )
            ),
            name=f"newbro_agent_{uuid4().hex[:8]}",
            channel=bootstrap.channel_name,
            agent_uid=bootstrap.agent_uid,
            remote_uids=["*"],
            enable_string_uid=False,
            expires_in=self._settings.client_token_ttl_seconds,
            debug=False,
            preset=_build_session_preset(self._settings),
        )

        try:
            runtime_session_id = await session.start()
        except httpx.ConnectError as exc:
            raise ConvoAIRuntimeError(
                "Failed to reach Agora ConvoAI endpoint "
                f"{state.client.get_current_url()} for area {self._settings.convoai_area}. "
                "Check network access or try another SYNAPSE_CONNECTOR_AGORA_CONVOAI_AREA."
            ) from exc

        runtime_session_id = str(runtime_session_id)
        diagnostics = ConnectorSessionDiagnostics(
            convoai_area=self._settings.convoai_area,
            selected_url=state.client.get_current_url(),
            runtime_session_id=runtime_session_id,
            asr_vendor=self._settings.asr.vendor,
            asr_credential_mode=self._settings.asr.credential_mode,
            asr_model=self._settings.asr.model,
            tts_vendor=self._settings.tts.vendor,
            tts_credential_mode=self._settings.tts.credential_mode,
            tts_model=self._settings.tts.model,
            agent_uid=bootstrap.agent_uid,
            agent_rtm_uid=bootstrap.agent_rtm_uid,
            rtc_uid=bootstrap.uid,
            rtm_user_id=bootstrap.user_rtm_uid,
            enable_string_uid=False,
            enable_rtm=(self._settings.data_channel == "rtm"),
            data_channel=self._settings.data_channel,
            enable_metrics=True,
            enable_error_message=True,
        )
        activated = ActivatedConvoAISession(
            prepared_session_id=bootstrap.prepared_session_id,
            runtime_session_id=runtime_session_id,
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
        self._sessions[runtime_session_id] = _LocalConvoAIHandle(
            bootstrap=activated,
            client=state.client,
            session=session,
        )
        return activated

    async def stop_session(self, runtime_session_id: str) -> None:
        try:
            handle = self._sessions.pop(runtime_session_id)
        except KeyError as exc:
            raise KeyError(f"Unknown runtime session id: {runtime_session_id}") from exc
        await handle.session.stop()

    async def speak(self, runtime_session_id: str, text: str) -> None:
        handle = self._sessions.get(runtime_session_id)
        if handle is None:
            raise KeyError(f"Unknown runtime session id: {runtime_session_id}")
        await handle.session.say(
            text=text,
            priority=self._settings.speak_priority,
            interruptable=self._settings.speak_interruptable,
        )

    def _load_sdk_types(self):
        from agora_agent import Agent, Area, AsyncAgentSession, AsyncAgora
        from agora_agent.agentkit import (
            AdvancedFeatures,
            DeepgramSTT,
            ElevenLabsTTS,
            MiniMaxTTS,
            OpenAI,
            OpenAITTS,
            SessionParams,
        )

        return (
            AsyncAgora,
            Area,
            Agent,
            AsyncAgentSession,
            DeepgramSTT,
            OpenAI,
            ElevenLabsTTS,
            MiniMaxTTS,
            OpenAITTS,
            AdvancedFeatures,
            SessionParams,
        )


def _build_asr_vendor(settings: AgoraConvoAIConnectorSettings, *, DeepgramSTT):
    if settings.asr.vendor != "deepgram":
        raise ConvoAIConfigurationError(f"Unsupported ASR vendor: {settings.asr.vendor}")
    kwargs: dict[str, object] = {
        "language": settings.asr.language,
        "model": settings.asr.model,
    }
    if settings.asr.credential_mode == "byok":
        kwargs["api_key"] = str(
            _require(settings.asr.api_key, _asr_api_key_requirement_name(settings))
        )
    return DeepgramSTT(**kwargs)


def _build_tts_vendor(
    settings: AgoraConvoAIConnectorSettings,
    *,
    ElevenLabsTTS,
    MiniMaxTTS,
    OpenAITTS,
):
    if settings.tts.credential_mode == "managed":
        if settings.tts.vendor == "minimax":
            kwargs: dict[str, object] = {"model": settings.tts.model}
            if settings.tts.voice:
                kwargs["voice_id"] = settings.tts.voice
            return MiniMaxTTS(**kwargs)
        if settings.tts.vendor == "openai":
            return OpenAITTS(model=settings.tts.model, voice=settings.tts.voice or "alloy")
        raise ConvoAIConfigurationError(
            f"Unsupported managed TTS vendor: {settings.tts.vendor}"
        )

    if settings.tts.vendor == "minimax":
        mm_kwargs: dict[str, object] = {
            "key": str(_require(settings.tts.api_key, _tts_api_key_requirement_name(settings))),
            "model": settings.tts.model,
        }
        if settings.tts.voice:
            mm_kwargs["voice_id"] = settings.tts.voice
        if settings.tts.sample_rate is not None:
            mm_kwargs["sample_rate"] = settings.tts.sample_rate
        return MiniMaxTTS(**mm_kwargs)

    if settings.tts.vendor != "elevenlabs":
        raise ConvoAIConfigurationError(f"Unsupported BYOK TTS vendor: {settings.tts.vendor}")

    kwargs = {
        "key": str(_require(settings.tts.api_key, _tts_api_key_requirement_name(settings))),
        "voice_id": str(_require(settings.tts.voice, _tts_voice_requirement_name(settings))),
        "model_id": settings.tts.model,
    }
    if settings.tts.sample_rate is not None:
        kwargs["sample_rate"] = settings.tts.sample_rate
    return ElevenLabsTTS(**kwargs)


def _build_session_preset(settings: AgoraConvoAIConnectorSettings) -> str | None:
    asr_preset_map = {"nova-2": "deepgram_nova_2", "nova-3": "deepgram_nova_3"}
    tts_preset_map = {
        ("minimax", "speech_2_6_turbo"): "minimax_speech_2_6_turbo",
        ("minimax", "speech_2_8_turbo"): "minimax_speech_2_8_turbo",
        ("openai", "tts-1"): "openai_tts_1",
    }
    presets: list[str] = []
    if settings.asr.credential_mode == "managed":
        preset = asr_preset_map.get(settings.asr.model)
        if preset is None:
            raise ConvoAIConfigurationError(
                f"Unsupported managed ASR model: {settings.asr.model}"
            )
        presets.append(preset)
    if settings.tts.credential_mode == "managed":
        preset = tts_preset_map.get((settings.tts.vendor, settings.tts.model))
        if preset is None:
            raise ConvoAIConfigurationError(
                f"Unsupported managed TTS vendor/model: {settings.tts.vendor}/{settings.tts.model}"
            )
        presets.append(preset)
    return ",".join(presets) or None


def _app_id_requirement_name(settings: AgoraConvoAIConnectorSettings) -> str:
    return (
        "connectors.agora-convoai.app_id"
        if settings.uses_yaml_config
        else "SYNAPSE_CONNECTOR_AGORA_CONVOAI_APP_ID"
    )


def _app_certificate_requirement_name(settings: AgoraConvoAIConnectorSettings) -> str:
    return (
        "connectors.agora-convoai.app_certificate"
        if settings.uses_yaml_config
        else "SYNAPSE_CONNECTOR_AGORA_CONVOAI_APP_CERTIFICATE"
    )


def _asr_api_key_requirement_name(settings: AgoraConvoAIConnectorSettings) -> str:
    return (
        "connectors.agora-convoai.asr.api_key"
        if settings.uses_yaml_config
        else "SYNAPSE_CONNECTOR_AGORA_CONVOAI_DEEPGRAM_API_KEY"
    )


def _tts_api_key_requirement_name(settings: AgoraConvoAIConnectorSettings) -> str:
    return (
        "connectors.agora-convoai.tts.api_key"
        if settings.uses_yaml_config
        else "SYNAPSE_CONNECTOR_AGORA_CONVOAI_ELEVENLABS_API_KEY"
    )


def _tts_voice_requirement_name(settings: AgoraConvoAIConnectorSettings) -> str:
    return (
        "connectors.agora-convoai.tts.voice"
        if settings.uses_yaml_config
        else "SYNAPSE_CONNECTOR_AGORA_CONVOAI_ELEVENLABS_VOICE_ID"
    )
