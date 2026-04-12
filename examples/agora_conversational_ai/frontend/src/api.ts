export interface FrontendConfig {
  ready: boolean;
  service_base_url: string;
  defaults: {
    profile?: string;
    channel_name?: string;
    display_name?: string;
  };
  missing_requirements: string[];
}

export interface FrontendSessionPrepareRequest {
  profile?: string;
  channel_name?: string;
  display_name?: string;
  user_id?: string;
}

export interface FrontendSessionActivateRequest {
  prepared_session_id: string;
}

export interface FrontendSessionDiagnostics {
  convoai_area: string;
  selected_url: string;
  runtime_agent_id: string | null;
  agent_uid: string;
  agent_rtm_uid: string;
  rtc_uid: string | number | null;
  rtm_user_id: string;
  enable_string_uid: boolean;
  enable_rtm: boolean;
  data_channel: string | null;
  enable_metrics: boolean;
  enable_error_message: boolean;
}

export interface FrontendPrepareResponse {
  prepared_session_id: string;
  app_id: string;
  channel_name: string;
  token: string;
  uid: number;
  user_rtm_uid: string;
  agent: {
    uid: string;
  };
  agent_rtm_uid: string;
  enable_string_uid: boolean;
  profile: string | null;
  display_name: string | null;
  diagnostics: FrontendSessionDiagnostics;
}

export interface FrontendActivateResponse {
  prepared_session_id: string;
  bridge_session_id: string;
  synapse_session_id: string;
  runtime_agent_id: string;
  chat_completions_url: string;
  app_id: string;
  channel_name: string;
  token: string;
  uid: number;
  user_rtm_uid: string;
  agent: {
    uid: string;
  };
  agent_rtm_uid: string;
  enable_string_uid: boolean;
  profile: string | null;
  display_name: string | null;
  diagnostics: FrontendSessionDiagnostics;
}

async function ensureOk(response: Response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response;
}

export async function getFrontendConfig(): Promise<FrontendConfig> {
  const response = await fetch("/frontend/config");
  return (await ensureOk(response)).json();
}

export async function prepareFrontendSession(
  payload: FrontendSessionPrepareRequest,
): Promise<FrontendPrepareResponse> {
  const response = await fetch("/frontend/session/prepare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await ensureOk(response)).json();
}

export async function activateFrontendSession(
  payload: FrontendSessionActivateRequest,
): Promise<FrontendActivateResponse> {
  const response = await fetch("/frontend/session/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await ensureOk(response)).json();
}

export async function stopFrontendSession(bridgeSessionId: string): Promise<void> {
  const response = await fetch("/frontend/session/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bridge_session_id: bridgeSessionId }),
  });
  await ensureOk(response);
}
