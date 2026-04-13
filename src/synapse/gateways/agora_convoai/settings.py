from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from synapse.envfile import load_env_file


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_first(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return None


@dataclass(slots=True)
class AgoraConvoAIGatewaySettings:
    service_base_url: str = "http://127.0.0.1:8010"
    synapse_base_url: str = "http://127.0.0.1:8000"
    default_app_id: str | None = None
    app_certificate: str | None = None
    convoai_area: str = "CN"
    deepgram_api_key: str | None = None
    deepgram_language: str = "en-US"
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    elevenlabs_sample_rate: int = 24000
    default_model: str = "synapse-agora-bridge"
    agent_instructions: str = "You are a helpful voice assistant."
    agent_greeting: str = "Hello. How can I help you today?"
    agent_uid: int = 9001
    user_uid: int = 101
    client_token_ttl_seconds: int = 3600
    sdk_debug: bool = False
    default_profile: str = "VOICE"
    default_channel_name: str = "synapse-voice-demo"
    default_display_name: str = "Synapse Tester"
    speak_priority: str = "APPEND"
    speak_interruptable: bool = True
    request_timeout_seconds: float = 10.0


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[4] / ".env.local"


def load_agora_gateway_settings(*, env_file: Path | None = None) -> AgoraConvoAIGatewaySettings:
    load_env_file(env_file or DEFAULT_ENV_FILE, override=False)
    service_base_url = _get_first(
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_SERVICE_BASE_URL",
        "SYNAPSE_GATEWAY_PUBLIC_BASE_URL",
    ) or "http://127.0.0.1:8010"
    synapse_base_url = _get_first(
        "SYNAPSE_GATEWAY_AGORA_CONVOAI_SYNAPSE_BASE_URL",
        "SYNAPSE_GATEWAY_SYNAPSE_BASE_URL",
    ) or "http://127.0.0.1:8000"
    return AgoraConvoAIGatewaySettings(
        service_base_url=service_base_url,
        synapse_base_url=synapse_base_url,
        default_app_id=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_ID",
            "AGORA_APP_ID",
        ),
        app_certificate=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_APP_CERTIFICATE",
            "AGORA_APP_CERTIFICATE",
        ),
        convoai_area=(
            _get_first("SYNAPSE_GATEWAY_AGORA_CONVOAI_AREA", "AGORA_CONVOAI_AREA") or "CN"
        ).upper(),
        deepgram_api_key=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_API_KEY",
            "DEEPGRAM_API_KEY",
        ),
        deepgram_language=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEEPGRAM_LANGUAGE",
            "AGORA_DEEPGRAM_LANGUAGE",
        )
        or "en-US",
        elevenlabs_api_key=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_API_KEY",
            "ELEVENLABS_API_KEY",
        ),
        elevenlabs_voice_id=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_VOICE_ID",
            "ELEVENLABS_VOICE_ID",
        ),
        elevenlabs_model_id=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_MODEL_ID",
            "AGORA_ELEVENLABS_MODEL_ID",
        )
        or "eleven_flash_v2_5",
        elevenlabs_sample_rate=int(
            _get_first(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_ELEVENLABS_SAMPLE_RATE",
                "AGORA_ELEVENLABS_SAMPLE_RATE",
            )
            or "24000"
        ),
        default_model=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_MODEL",
            "AGORA_BRIDGE_MODEL",
        )
        or "synapse-agora-bridge",
        agent_instructions=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_AGENT_INSTRUCTIONS",
            "AGORA_CONVOAI_AGENT_INSTRUCTIONS",
        )
        or "You are a helpful voice assistant.",
        agent_greeting=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_AGENT_GREETING",
            "AGORA_CONVOAI_AGENT_GREETING",
        )
        or "Hello. How can I help you today?",
        agent_uid=int(
            _get_first(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_AGENT_UID",
                "AGORA_CONVOAI_AGENT_UID",
            )
            or "9001"
        ),
        user_uid=int(
            _get_first(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_USER_UID",
                "AGORA_CONVOAI_USER_UID",
            )
            or "101"
        ),
        client_token_ttl_seconds=int(
            _get_first(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_CLIENT_TOKEN_TTL_SECONDS",
                "AGORA_CLIENT_TOKEN_TTL_SECONDS",
            )
            or "3600"
        ),
        sdk_debug=_get_bool(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_SDK_DEBUG",
            _get_bool("AGORA_CONVOAI_SDK_DEBUG", False),
        ),
        default_profile=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEFAULT_PROFILE",
            "AGORA_FRONTEND_DEFAULT_PROFILE",
        )
        or "VOICE",
        default_channel_name=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEFAULT_CHANNEL_NAME",
            "AGORA_FRONTEND_DEFAULT_CHANNEL_NAME",
        )
        or "synapse-voice-demo",
        default_display_name=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_DEFAULT_DISPLAY_NAME",
            "AGORA_FRONTEND_DEFAULT_DISPLAY_NAME",
        )
        or "Synapse Tester",
        speak_priority=_get_first(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_SPEAK_PRIORITY",
            "AGORA_BRIDGE_SPEAK_PRIORITY",
        )
        or "APPEND",
        speak_interruptable=_get_bool(
            "SYNAPSE_GATEWAY_AGORA_CONVOAI_SPEAK_INTERRUPTABLE",
            _get_bool("AGORA_BRIDGE_SPEAK_INTERRUPTABLE", True),
        ),
        request_timeout_seconds=float(
            _get_first(
                "SYNAPSE_GATEWAY_AGORA_CONVOAI_REQUEST_TIMEOUT_SECONDS",
                "AGORA_BRIDGE_REQUEST_TIMEOUT_SECONDS",
            )
            or "10"
        ),
    )
