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


class FrontendConfigResponse(BaseModel):
    ready: bool
    service_base_url: str
    defaults: "FrontendSessionDefaults"
    missing_requirements: list[str] = Field(default_factory=list)


class FrontendSessionDefaults(BaseModel):
    profile: str
    channel_name: str
    display_name: str
    agent_instructions: str
    agent_greeting: str
    agent_uid: int
    user_uid: int


class FrontendSessionPrepareRequest(BaseModel):
    profile: str | None = None
    channel_name: str | None = None
    display_name: str | None = None
    agent_instructions: str | None = None
    agent_greeting: str | None = None
    agent_uid: int | None = None
    user_uid: int | None = None


class FrontendSessionActivateRequest(BaseModel):
    prepared_session_id: str


class FrontendSessionDiagnostics(BaseModel):
    convoai_area: str
    selected_url: str
    runtime_agent_id: str | None = None
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


class FrontendPrepareAgentModel(BaseModel):
    uid: str


class FrontendSessionPrepareResponse(BaseModel):
    prepared_session_id: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    user_rtm_uid: str
    agent: FrontendPrepareAgentModel
    agent_rtm_uid: str
    enable_string_uid: bool = False
    profile: str | None = None
    display_name: str | None = None
    diagnostics: FrontendSessionDiagnostics


class FrontendSessionActivateResponse(BaseModel):
    prepared_session_id: str
    bridge_session_id: str
    synapse_session_id: str
    runtime_agent_id: str
    chat_completions_url: str
    app_id: str
    channel_name: str
    token: str
    uid: int
    user_rtm_uid: str
    agent: FrontendPrepareAgentModel
    agent_rtm_uid: str
    enable_string_uid: bool = False
    profile: str | None = None
    display_name: str | None = None
    diagnostics: FrontendSessionDiagnostics


class FrontendSessionStopRequest(BaseModel):
    bridge_session_id: str


class FrontendSessionStopResponse(BaseModel):
    status: str = "stopped"
