from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = False


class GatewaySessionDefaults(BaseModel):
    profile: str
    channel_name: str
    display_name: str
    agent_instructions: str
    agent_greeting: str
    agent_uid: int
    user_uid: int


class GatewayConfigResponse(BaseModel):
    ready: bool
    service_base_url: str
    defaults: GatewaySessionDefaults
    missing_requirements: list[str] = Field(default_factory=list)


class GatewaySessionPrepareRequest(BaseModel):
    profile: str | None = None
    channel_name: str | None = None
    display_name: str | None = None
    agent_instructions: str | None = None
    agent_greeting: str | None = None
    agent_uid: int | None = None
    user_uid: int | None = None


class GatewaySessionActivateRequest(BaseModel):
    prepared_session_id: str


class GatewaySessionDiagnostics(BaseModel):
    convoai_area: str
    selected_url: str
    runtime_session_id: str | None = None
    asr_vendor: str
    asr_credential_mode: str
    asr_model: str
    tts_vendor: str
    tts_credential_mode: str
    tts_model: str
    agent_uid: str
    agent_rtm_uid: str
    rtc_uid: str | int | None = None
    rtm_user_id: str
    enable_string_uid: bool
    enable_rtm: bool
    data_channel: str | None = None
    enable_metrics: bool
    enable_error_message: bool


class GatewayPrepareAgentModel(BaseModel):
    uid: str


class GatewaySessionPrepareResponse(BaseModel):
    prepared_session_id: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    user_rtm_uid: str
    agent: GatewayPrepareAgentModel
    agent_rtm_uid: str
    enable_string_uid: bool = False
    profile: str | None = None
    display_name: str | None = None
    diagnostics: GatewaySessionDiagnostics


class GatewaySessionActivateResponse(BaseModel):
    prepared_session_id: str
    binding_id: str
    synapse_session_id: str
    runtime_session_id: str
    chat_completions_url: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    user_rtm_uid: str
    agent: GatewayPrepareAgentModel
    agent_rtm_uid: str
    enable_string_uid: bool = False
    profile: str | None = None
    display_name: str | None = None
    diagnostics: GatewaySessionDiagnostics


class GatewaySessionStopRequest(BaseModel):
    binding_id: str


class GatewaySessionStopResponse(BaseModel):
    status: str = "stopped"
