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


class ConnectorSessionDefaults(BaseModel):
    profile: str
    channel_name: str | None = None
    display_name: str
    agent_instructions: str
    agent_greeting: str
    agent_uid: int
    user_uid: int


class ConnectorConfigResponse(BaseModel):
    ready: bool
    service_base_url: str
    defaults: ConnectorSessionDefaults
    missing_requirements: list[str] = Field(default_factory=list)


class ConnectorSessionPrepareRequest(BaseModel):
    synapse_session_id: str | None = None
    profile: str | None = None
    channel_name: str | None = None
    display_name: str | None = None
    agent_instructions: str | None = None
    agent_greeting: str | None = None
    agent_uid: int | None = None
    user_uid: int | None = None


class ConnectorSessionActivateRequest(BaseModel):
    prepared_session_id: str


class ConnectorSessionDiagnostics(BaseModel):
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


class ConnectorPrepareAgentModel(BaseModel):
    uid: str


class ConnectorSessionPrepareResponse(BaseModel):
    prepared_session_id: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    user_rtm_uid: str
    agent: ConnectorPrepareAgentModel
    agent_rtm_uid: str
    enable_string_uid: bool = False
    profile: str | None = None
    display_name: str | None = None
    diagnostics: ConnectorSessionDiagnostics


class ConnectorSessionActivateResponse(BaseModel):
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
    agent: ConnectorPrepareAgentModel
    agent_rtm_uid: str
    enable_string_uid: bool = False
    profile: str | None = None
    display_name: str | None = None
    diagnostics: ConnectorSessionDiagnostics


class ConnectorSessionStopRequest(BaseModel):
    binding_id: str


class ConnectorSessionStopResponse(BaseModel):
    status: str = "stopped"


class SttSessionStartRequest(BaseModel):
    prepared_stt_session_id: str
    languages: list[str] | None = None


class SttSessionPrepareRequest(BaseModel):
    synapse_session_id: str
    assigned_bro_id: str
    user_uid: int | None = None


class SttSessionPrepareResponse(BaseModel):
    prepared_stt_session_id: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    status: str = "prepared"


class SttSessionStartResponse(BaseModel):
    stt_session_id: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    pub_bot_uid: int
    sub_bot_uid: int
    agent_id: str
    status: str


class SttSessionQueryResponse(BaseModel):
    stt_session_id: str
    agent_id: str
    status: str
    raw: dict[str, Any] = Field(default_factory=dict)


class SttSessionHeartbeatRequest(BaseModel):
    stt_session_id: str


class SttSessionHeartbeatResponse(BaseModel):
    status: str = "active"


class SttSessionLeaveRequest(BaseModel):
    stt_session_id: str | None = None
    prepared_stt_session_id: str | None = None


class SttSessionStopRequest(BaseModel):
    stt_session_id: str


class SttSessionStopResponse(BaseModel):
    status: str = "stopped"
