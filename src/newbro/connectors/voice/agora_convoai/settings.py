from __future__ import annotations
from dataclasses import dataclass, field
import os
from pathlib import Path

from newbro.config_home import SYNAPSE_ENV_FILE
from newbro.envfile import load_env_file
from newbro.connectors.host.config import ConnectorConfigError, load_connector_config


AGORA_BRIDGE_MODEL = "newbro-agora-bridge"
DEFAULT_AGENT_INSTRUCTIONS = "You are a helpful voice assistant."
DEFAULT_AGENT_GREETING = "Hello. How can I help you today?"
DEFAULT_PROFILE = "VOICE"
DEFAULT_DISPLAY_NAME = "Newbro Tester"
DEFAULT_STT_LANGUAGES = ("zh-CN",)


@dataclass(slots=True)
class AgoraConvoAIASRSettings:
    vendor: str = "openai"
    credential_mode: str = "shared"
    model: str = "gpt-4o-transcribe"
    language: str = "zh"
    api_key: str | None = None


@dataclass(slots=True)
class AgoraConvoAISttSettings:
    enabled: bool = True
    languages: tuple[str, ...] = DEFAULT_STT_LANGUAGES
    max_idle_time: int = 60
    token_ttl_seconds: int = 3600
    query_interval_seconds: float = 1.0


@dataclass(slots=True)
class AgoraConvoAITTSSettings:
    vendor: str = "minimax"
    credential_mode: str = "managed"
    model: str = "speech_2_6_turbo"
    voice: str | None = "English_magnetic_voiced_man"
    api_key: str | None = None
    sample_rate: int | None = None


@dataclass(slots=True)
class AgoraConvoAIConnectorSettings:
    uses_yaml_config: bool = False
    service_base_url: str = "http://127.0.0.1:8010"
    synapse_base_url: str = "http://127.0.0.1:8000"
    synapse_api_bearer_token: str | None = None
    cloudflare_access_client_id: str | None = None
    cloudflare_access_client_secret: str | None = None
    app_id: str | None = None
    app_certificate: str | None = None
    convoai_area: str = "US"
    asr: AgoraConvoAIASRSettings = field(default_factory=AgoraConvoAIASRSettings)
    stt: AgoraConvoAISttSettings = field(default_factory=AgoraConvoAISttSettings)
    tts: AgoraConvoAITTSSettings = field(default_factory=AgoraConvoAITTSSettings)
    agent_instructions: str = DEFAULT_AGENT_INSTRUCTIONS
    agent_greeting: str = DEFAULT_AGENT_GREETING
    agent_uid: int = 9001
    user_uid: int = 101
    client_token_ttl_seconds: int = 3600
    sdk_debug: bool = False
    default_profile: str = DEFAULT_PROFILE
    default_display_name: str = DEFAULT_DISPLAY_NAME
    data_channel: str = "rtm"
    conversation_brain_prompt: str = ""
    dispatch_trigger_phrases: tuple[str, ...] = ()
    speak_priority: str = "APPEND"
    speak_interruptable: bool = True
    request_timeout_seconds: float = 10.0
    openai_api_key: str | None = None


DEFAULT_ENV_FILE = SYNAPSE_ENV_FILE


def load_agora_connector_settings(*, env_file: Path | None = None) -> AgoraConvoAIConnectorSettings:
    env_path = env_file or DEFAULT_ENV_FILE
    load_env_file(env_path, override=False)
    loaded_connector_config = load_connector_config(env_file=env_path)
    if loaded_connector_config.source_path is None:
        return AgoraConvoAIConnectorSettings(
            uses_yaml_config=True,
            service_base_url=loaded_connector_config.host_settings.public_base_url,
            synapse_base_url=loaded_connector_config.host_settings.synapse_base_url,
            synapse_api_bearer_token=os.getenv("SYNAPSE_API_BEARER_TOKEN") or None,
            cloudflare_access_client_id=os.getenv("SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_ID") or None,
            cloudflare_access_client_secret=os.getenv("SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_SECRET")
            or None,
            app_id=None,
            app_certificate=None,
            convoai_area="US",
            asr=AgoraConvoAIASRSettings(),
            stt=AgoraConvoAISttSettings(),
            tts=AgoraConvoAITTSSettings(),
            agent_instructions=DEFAULT_AGENT_INSTRUCTIONS,
            agent_greeting=DEFAULT_AGENT_GREETING,
            agent_uid=9001,
            user_uid=101,
            client_token_ttl_seconds=3600,
            sdk_debug=False,
            default_profile=DEFAULT_PROFILE,
            default_display_name=DEFAULT_DISPLAY_NAME,
            data_channel="rtm",
            conversation_brain_prompt="",
            dispatch_trigger_phrases=(),
            speak_priority="APPEND",
            speak_interruptable=True,
            request_timeout_seconds=10.0,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        )
    return _load_agora_connector_settings_from_yaml(loaded_connector_config)


def _load_agora_connector_settings_from_yaml(loaded_connector_config) -> AgoraConvoAIConnectorSettings:
    source_path = loaded_connector_config.source_path
    assert source_path is not None
    raw_connector = loaded_connector_config.connectors.get("agora-convoai")
    if raw_connector is None:
        raise ConnectorConfigError(
            f"Missing 'connectors.agora-convoai' section in {source_path}"
        )
    if not isinstance(raw_connector, dict):
        raise ConnectorConfigError(
            f"'connectors.agora-convoai' must be a mapping in {source_path}"
        )

    host_settings = loaded_connector_config.host_settings
    asr = _parse_yaml_asr_settings(raw_connector.get("asr"), source_path)
    stt = _parse_yaml_stt_settings(raw_connector.get("stt"), source_path)
    tts = _parse_yaml_tts_settings(raw_connector.get("tts"), source_path)
    return AgoraConvoAIConnectorSettings(
        uses_yaml_config=True,
        service_base_url=host_settings.public_base_url,
        synapse_base_url=host_settings.synapse_base_url,
        synapse_api_bearer_token=os.getenv("SYNAPSE_API_BEARER_TOKEN") or None,
        cloudflare_access_client_id=os.getenv("SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_ID") or None,
        cloudflare_access_client_secret=os.getenv("SYNAPSE_CLOUDFLARE_ACCESS_CLIENT_SECRET")
        or None,
        app_id=_read_optional_string(raw_connector, "app_id", source_path),
        app_certificate=_read_optional_string(raw_connector, "app_certificate", source_path),
        convoai_area="US",
        asr=asr,
        stt=stt,
        tts=tts,
        agent_instructions=DEFAULT_AGENT_INSTRUCTIONS,
        agent_greeting=DEFAULT_AGENT_GREETING,
        agent_uid=9001,
        user_uid=101,
        client_token_ttl_seconds=int(raw_connector.get("client_token_ttl_seconds", 3600)),
        sdk_debug=False,
        default_profile=DEFAULT_PROFILE,
        default_display_name=DEFAULT_DISPLAY_NAME,
        data_channel=str(raw_connector.get("data_channel", "rtm")).lower(),
        conversation_brain_prompt=str(raw_connector.get("conversation_brain_prompt", "") or ""),
        dispatch_trigger_phrases=_parse_csv_list(
            raw_connector.get("dispatch_trigger_phrases", ""),
        ),
        speak_priority=str(raw_connector.get("speak_priority", "APPEND")).upper(),
        speak_interruptable=_parse_bool_scalar(
            raw_connector.get("speak_interruptable", True),
            field_name="connectors.agora-convoai.speak_interruptable",
            source_path=source_path,
        ),
        request_timeout_seconds=float(raw_connector.get("request_timeout_seconds", 10.0)),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
    )


def _parse_yaml_asr_settings(raw_asr, source_path: Path) -> AgoraConvoAIASRSettings:
    if raw_asr is None:
        raw_asr = {}
    if not isinstance(raw_asr, dict):
        raise ConnectorConfigError(f"'connectors.agora-convoai.asr' must be a mapping in {source_path}")
    settings = AgoraConvoAIASRSettings(
        vendor=str(raw_asr.get("vendor", "openai")).lower(),
        credential_mode=str(raw_asr.get("credential_mode", "shared")).lower(),
        model=str(raw_asr.get("model", "gpt-4o-transcribe")),
        language=str(raw_asr.get("language", "zh")),
        api_key=_read_optional_string(raw_asr, "api_key", source_path),
    )
    if settings.vendor not in {"deepgram", "openai"}:
        raise ConnectorConfigError(
            f"Unsupported ASR vendor '{settings.vendor}' in {source_path}; use 'openai' or 'deepgram'"
        )
    supported_credential_modes = {
        "deepgram": {"managed", "byok"},
        "openai": {"shared", "byok"},
    }
    if settings.credential_mode not in supported_credential_modes[settings.vendor]:
        raise ConnectorConfigError(
            f"Unsupported ASR credential_mode '{settings.credential_mode}' in {source_path}"
        )
    if settings.vendor == "deepgram" and settings.credential_mode == "managed" and settings.model not in {"nova-2", "nova-3"}:
        raise ConnectorConfigError(
            f"Unsupported managed ASR model '{settings.model}' in {source_path}"
        )
    if settings.vendor == "openai" and settings.model not in {"gpt-4o-transcribe", "whisper-1"}:
        raise ConnectorConfigError(
            f"Unsupported OpenAI ASR model '{settings.model}' in {source_path}"
        )
    return settings



def _parse_yaml_stt_settings(raw_stt, source_path: Path) -> AgoraConvoAISttSettings:
    if raw_stt is None:
        raw_stt = {}
    if not isinstance(raw_stt, dict):
        raise ConnectorConfigError(f"'connectors.agora-convoai.stt' must be a mapping in {source_path}")
    raw_languages = raw_stt.get("languages", list(DEFAULT_STT_LANGUAGES))
    if isinstance(raw_languages, str):
        languages = tuple(part.strip() for part in raw_languages.split(",") if part.strip())
    elif isinstance(raw_languages, list):
        languages = tuple(str(item).strip() for item in raw_languages if str(item).strip())
    else:
        raise ConnectorConfigError(f"'connectors.agora-convoai.stt.languages' must be a string or list in {source_path}")
    if not languages:
        languages = DEFAULT_STT_LANGUAGES
    return AgoraConvoAISttSettings(
        enabled=_parse_bool_scalar(
            raw_stt.get("enabled", True),
            field_name="connectors.agora-convoai.stt.enabled",
            source_path=source_path,
        ),
        languages=languages,
        max_idle_time=int(raw_stt.get("max_idle_time", 60)),
        token_ttl_seconds=int(raw_stt.get("token_ttl_seconds", 3600)),
        query_interval_seconds=float(raw_stt.get("query_interval_seconds", 1.0)),
    )

def _parse_yaml_tts_settings(raw_tts, source_path: Path) -> AgoraConvoAITTSSettings:
    if raw_tts is None:
        raw_tts = {}
    if not isinstance(raw_tts, dict):
        raise ConnectorConfigError(f"'connectors.agora-convoai.tts' must be a mapping in {source_path}")
    settings = AgoraConvoAITTSSettings(
        vendor=str(raw_tts.get("vendor", "minimax")).lower(),
        credential_mode=str(raw_tts.get("credential_mode", "managed")).lower(),
        model=str(raw_tts.get("model", "speech_2_6_turbo")),
        voice=_read_optional_string(raw_tts, "voice", source_path) or (
            "English_magnetic_voiced_man"
            if str(raw_tts.get("vendor", "minimax")).lower() == "minimax"
            else None
        ),
        api_key=_read_optional_string(raw_tts, "api_key", source_path),
        sample_rate=(
            int(raw_tts["sample_rate"])
            if raw_tts.get("sample_rate") not in (None, "")
            else None
        ),
    )
    if settings.credential_mode not in {"managed", "byok"}:
        raise ConnectorConfigError(
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
        raise ConnectorConfigError(
            f"Unsupported managed TTS vendor/model '{settings.vendor}/{settings.model}' in {source_path}"
        )
    if settings.credential_mode == "byok" and settings.vendor != "elevenlabs":
        raise ConnectorConfigError(
            f"Unsupported BYOK TTS vendor '{settings.vendor}' in {source_path}; use 'elevenlabs'"
        )
    return settings


def _read_optional_string(raw: dict[str, object], key: str, source_path: Path) -> str | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, (str, int, float, bool)):
        raise ConnectorConfigError(f"'{key}' must be a scalar in {source_path}")
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
    raise ConnectorConfigError(f"'{field_name}' must be a boolean in {source_path}")


def _parse_csv_list(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),) if str(value).strip() else ()
