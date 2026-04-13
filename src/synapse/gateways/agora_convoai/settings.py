from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from synapse.config_home import SYNAPSE_ENV_FILE
from synapse.envfile import load_env_file
from synapse.gateway_host.config import GatewayConfigError, load_gateway_config


AGORA_BRIDGE_MODEL = "synapse-agora-bridge"
DEFAULT_AGENT_INSTRUCTIONS = "You are a helpful voice assistant."
DEFAULT_AGENT_GREETING = "Hello. How can I help you today?"
DEFAULT_PROFILE = "VOICE"
DEFAULT_CHANNEL_NAME = "synapse-voice-demo"
DEFAULT_DISPLAY_NAME = "Synapse Tester"


@dataclass(slots=True)
class AgoraConvoAIASRSettings:
    vendor: str = "deepgram"
    credential_mode: str = "managed"
    model: str = "nova-3"
    language: str = "en-US"
    api_key: str | None = None


@dataclass(slots=True)
class AgoraConvoAITTSSettings:
    vendor: str = "minimax"
    credential_mode: str = "managed"
    model: str = "speech_2_6_turbo"
    voice: str | None = None
    api_key: str | None = None
    sample_rate: int | None = None


@dataclass(slots=True)
class AgoraConvoAIGatewaySettings:
    uses_yaml_config: bool = False
    service_base_url: str = "http://127.0.0.1:8010"
    synapse_base_url: str = "http://127.0.0.1:8000"
    app_id: str | None = None
    app_certificate: str | None = None
    convoai_area: str = "CN"
    asr: AgoraConvoAIASRSettings = field(default_factory=AgoraConvoAIASRSettings)
    tts: AgoraConvoAITTSSettings = field(default_factory=AgoraConvoAITTSSettings)
    agent_instructions: str = DEFAULT_AGENT_INSTRUCTIONS
    agent_greeting: str = DEFAULT_AGENT_GREETING
    agent_uid: int = 9001
    user_uid: int = 101
    client_token_ttl_seconds: int = 3600
    sdk_debug: bool = False
    default_profile: str = DEFAULT_PROFILE
    default_channel_name: str = DEFAULT_CHANNEL_NAME
    default_display_name: str = DEFAULT_DISPLAY_NAME
    speak_priority: str = "APPEND"
    speak_interruptable: bool = True
    request_timeout_seconds: float = 10.0


DEFAULT_ENV_FILE = SYNAPSE_ENV_FILE


def load_agora_gateway_settings(*, env_file: Path | None = None) -> AgoraConvoAIGatewaySettings:
    env_path = env_file or DEFAULT_ENV_FILE
    load_env_file(env_path, override=False)
    loaded_gateway_config = load_gateway_config(env_file=env_path)
    if loaded_gateway_config.source_path is None:
        return AgoraConvoAIGatewaySettings(
            uses_yaml_config=True,
            service_base_url=loaded_gateway_config.host_settings.public_base_url,
            synapse_base_url=loaded_gateway_config.host_settings.synapse_base_url,
            app_id=None,
            app_certificate=None,
            convoai_area="CN",
            asr=AgoraConvoAIASRSettings(),
            tts=AgoraConvoAITTSSettings(),
            agent_instructions=DEFAULT_AGENT_INSTRUCTIONS,
            agent_greeting=DEFAULT_AGENT_GREETING,
            agent_uid=9001,
            user_uid=101,
            client_token_ttl_seconds=3600,
            sdk_debug=False,
            default_profile=DEFAULT_PROFILE,
            default_channel_name=DEFAULT_CHANNEL_NAME,
            default_display_name=DEFAULT_DISPLAY_NAME,
            speak_priority="APPEND",
            speak_interruptable=True,
            request_timeout_seconds=10.0,
        )
    return _load_agora_gateway_settings_from_yaml(loaded_gateway_config)


def _load_agora_gateway_settings_from_yaml(loaded_gateway_config) -> AgoraConvoAIGatewaySettings:
    source_path = loaded_gateway_config.source_path
    assert source_path is not None
    raw_gateway = loaded_gateway_config.gateways.get("agora-convoai")
    if raw_gateway is None:
        raise GatewayConfigError(
            f"Missing 'gateways.agora-convoai' section in {source_path}"
        )
    if not isinstance(raw_gateway, dict):
        raise GatewayConfigError(
            f"'gateways.agora-convoai' must be a mapping in {source_path}"
        )

    host_settings = loaded_gateway_config.host_settings
    asr = _parse_yaml_asr_settings(raw_gateway.get("asr"), source_path)
    tts = _parse_yaml_tts_settings(raw_gateway.get("tts"), source_path)
    return AgoraConvoAIGatewaySettings(
        uses_yaml_config=True,
        service_base_url=host_settings.public_base_url,
        synapse_base_url=host_settings.synapse_base_url,
        app_id=_read_optional_string(raw_gateway, "app_id", source_path),
        app_certificate=_read_optional_string(raw_gateway, "app_certificate", source_path),
        convoai_area=str(raw_gateway.get("convoai_area", "CN")).upper(),
        asr=asr,
        tts=tts,
        agent_instructions=DEFAULT_AGENT_INSTRUCTIONS,
        agent_greeting=DEFAULT_AGENT_GREETING,
        agent_uid=9001,
        user_uid=101,
        client_token_ttl_seconds=int(raw_gateway.get("client_token_ttl_seconds", 3600)),
        sdk_debug=False,
        default_profile=DEFAULT_PROFILE,
        default_channel_name=DEFAULT_CHANNEL_NAME,
        default_display_name=DEFAULT_DISPLAY_NAME,
        speak_priority=str(raw_gateway.get("speak_priority", "APPEND")).upper(),
        speak_interruptable=_parse_bool_scalar(
            raw_gateway.get("speak_interruptable", True),
            field_name="gateways.agora-convoai.speak_interruptable",
            source_path=source_path,
        ),
        request_timeout_seconds=float(raw_gateway.get("request_timeout_seconds", 10.0)),
    )


def _parse_yaml_asr_settings(raw_asr, source_path: Path) -> AgoraConvoAIASRSettings:
    if raw_asr is None:
        raw_asr = {}
    if not isinstance(raw_asr, dict):
        raise GatewayConfigError(f"'gateways.agora-convoai.asr' must be a mapping in {source_path}")
    settings = AgoraConvoAIASRSettings(
        vendor=str(raw_asr.get("vendor", "deepgram")).lower(),
        credential_mode=str(raw_asr.get("credential_mode", "managed")).lower(),
        model=str(raw_asr.get("model", "nova-3")),
        language=str(raw_asr.get("language", "en-US")),
        api_key=_read_optional_string(raw_asr, "api_key", source_path),
    )
    if settings.vendor != "deepgram":
        raise GatewayConfigError(
            f"Unsupported ASR vendor '{settings.vendor}' in {source_path}; use 'deepgram'"
        )
    if settings.credential_mode not in {"managed", "byok"}:
        raise GatewayConfigError(
            f"Unsupported ASR credential_mode '{settings.credential_mode}' in {source_path}"
        )
    if settings.credential_mode == "managed" and settings.model not in {"nova-2", "nova-3"}:
        raise GatewayConfigError(
            f"Unsupported managed ASR model '{settings.model}' in {source_path}"
        )
    return settings


def _parse_yaml_tts_settings(raw_tts, source_path: Path) -> AgoraConvoAITTSSettings:
    if raw_tts is None:
        raw_tts = {}
    if not isinstance(raw_tts, dict):
        raise GatewayConfigError(f"'gateways.agora-convoai.tts' must be a mapping in {source_path}")
    settings = AgoraConvoAITTSSettings(
        vendor=str(raw_tts.get("vendor", "minimax")).lower(),
        credential_mode=str(raw_tts.get("credential_mode", "managed")).lower(),
        model=str(raw_tts.get("model", "speech_2_6_turbo")),
        voice=_read_optional_string(raw_tts, "voice", source_path),
        api_key=_read_optional_string(raw_tts, "api_key", source_path),
        sample_rate=(
            int(raw_tts["sample_rate"])
            if raw_tts.get("sample_rate") not in (None, "")
            else None
        ),
    )
    if settings.credential_mode not in {"managed", "byok"}:
        raise GatewayConfigError(
            f"Unsupported TTS credential_mode '{settings.credential_mode}' in {source_path}"
        )
    valid_managed_tts = {
        ("minimax", "speech_2_6_turbo"),
        ("minimax", "speech_2_8_turbo"),
        ("openai", "tts-1"),
    }
    if settings.credential_mode == "managed" and (
        settings.vendor,
        settings.model,
    ) not in valid_managed_tts:
        raise GatewayConfigError(
            f"Unsupported managed TTS vendor/model '{settings.vendor}/{settings.model}' in {source_path}"
        )
    if settings.credential_mode == "byok" and settings.vendor != "elevenlabs":
        raise GatewayConfigError(
            f"Unsupported BYOK TTS vendor '{settings.vendor}' in {source_path}; use 'elevenlabs'"
        )
    return settings


def _read_optional_string(raw: dict[str, object], key: str, source_path: Path) -> str | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, (str, int, float, bool)):
        raise GatewayConfigError(f"'{key}' must be a scalar in {source_path}")
    return str(value)


def _parse_bool_scalar(value: object, *, field_name: str, source_path: Path) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise GatewayConfigError(f"'{field_name}' must be a boolean in {source_path}")
