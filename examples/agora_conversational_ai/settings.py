from __future__ import annotations

import os
from dataclasses import dataclass

from synapse.config_home import SYNAPSE_ENV_FILE
from synapse.gateways.agora_convoai.settings import (
    DEFAULT_AGENT_GREETING,
    DEFAULT_AGENT_INSTRUCTIONS,
    DEFAULT_CHANNEL_NAME,
    DEFAULT_DISPLAY_NAME,
    DEFAULT_PROFILE,
)
from synapse.runtime import config as runtime_config_module


EXAMPLE_LOCAL_ENV_FILE = SYNAPSE_ENV_FILE


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class AgoraBridgeSettings:
    service_base_url: str = "http://127.0.0.1:8010"
    synapse_base_url: str = "http://127.0.0.1:8000"
    app_id: str | None = None
    app_certificate: str | None = None
    convoai_area: str = "CN"
    deepgram_api_key: str | None = None
    deepgram_language: str = "en-US"
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    elevenlabs_sample_rate: int = 24000
    agent_instructions: str = DEFAULT_AGENT_INSTRUCTIONS
    agent_greeting: str = DEFAULT_AGENT_GREETING
    agent_uid: int = 9001
    user_uid: int = 101
    client_token_ttl_seconds: int = 3600
    sdk_debug: bool = False
    frontend_default_profile: str = DEFAULT_PROFILE
    frontend_default_channel_name: str = DEFAULT_CHANNEL_NAME
    frontend_default_display_name: str = DEFAULT_DISPLAY_NAME
    speak_priority: str = "APPEND"
    speak_interruptable: bool = True
    request_timeout_seconds: float = 10.0


def configure_example_env() -> None:
    runtime_config_module.LOCAL_ENV_FILE = EXAMPLE_LOCAL_ENV_FILE


def load_bridge_settings() -> AgoraBridgeSettings:
    configure_example_env()
    runtime_config_module.load_local_env()
    return AgoraBridgeSettings(
        service_base_url=os.getenv("AGORA_BRIDGE_SERVICE_BASE_URL", "http://127.0.0.1:8010"),
        synapse_base_url=os.getenv(
            "AGORA_BRIDGE_SYNAPSE_BASE_URL",
            "http://127.0.0.1:8000",
        ),
        app_id=os.getenv("AGORA_APP_ID") or None,
        app_certificate=os.getenv("AGORA_APP_CERTIFICATE") or None,
        convoai_area=os.getenv("AGORA_CONVOAI_AREA", "CN").upper(),
        deepgram_api_key=os.getenv("DEEPGRAM_API_KEY") or None,
        deepgram_language=os.getenv("AGORA_DEEPGRAM_LANGUAGE", "en-US"),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY") or None,
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID") or None,
        elevenlabs_model_id=os.getenv("AGORA_ELEVENLABS_MODEL_ID", "eleven_flash_v2_5"),
        elevenlabs_sample_rate=int(os.getenv("AGORA_ELEVENLABS_SAMPLE_RATE", "24000")),
        agent_instructions=os.getenv(
            "AGORA_CONVOAI_AGENT_INSTRUCTIONS",
            DEFAULT_AGENT_INSTRUCTIONS,
        ),
        agent_greeting=os.getenv(
            "AGORA_CONVOAI_AGENT_GREETING",
            DEFAULT_AGENT_GREETING,
        ),
        agent_uid=int(os.getenv("AGORA_CONVOAI_AGENT_UID", "9001")),
        user_uid=int(os.getenv("AGORA_CONVOAI_USER_UID", "101")),
        client_token_ttl_seconds=int(os.getenv("AGORA_CLIENT_TOKEN_TTL_SECONDS", "3600")),
        sdk_debug=_get_bool("AGORA_CONVOAI_SDK_DEBUG", False),
        frontend_default_profile=os.getenv("AGORA_FRONTEND_DEFAULT_PROFILE", DEFAULT_PROFILE),
        frontend_default_channel_name=os.getenv(
            "AGORA_FRONTEND_DEFAULT_CHANNEL_NAME",
            DEFAULT_CHANNEL_NAME,
        ),
        frontend_default_display_name=os.getenv(
            "AGORA_FRONTEND_DEFAULT_DISPLAY_NAME",
            DEFAULT_DISPLAY_NAME,
        ),
        speak_priority=os.getenv("AGORA_BRIDGE_SPEAK_PRIORITY", "APPEND").upper(),
        speak_interruptable=_get_bool("AGORA_BRIDGE_SPEAK_INTERRUPTABLE", True),
        request_timeout_seconds=float(os.getenv("AGORA_BRIDGE_REQUEST_TIMEOUT_SECONDS", "10")),
    )
