export interface GatewayConfig {
  ready: boolean;
  service_base_url: string;
  defaults: {
    profile?: string;
    channel_name?: string;
    display_name?: string;
    agent_instructions?: string;
    agent_greeting?: string;
    agent_uid?: number;
    user_uid?: number;
  };
  missing_requirements: string[];
}

export interface GatewaySessionPrepareRequest {
  profile?: string;
  channel_name?: string;
  display_name?: string;
  agent_instructions?: string;
  agent_greeting?: string;
  agent_uid?: number;
  user_uid?: number;
}

export interface GatewaySessionActivateRequest {
  prepared_session_id: string;
}

export interface GatewaySessionDiagnostics {
  convoai_area: string;
  selected_url: string;
  runtime_session_id: string | null;
  asr_vendor: string;
  asr_credential_mode: string;
  asr_model: string;
  tts_vendor: string;
  tts_credential_mode: string;
  tts_model: string;
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

export interface GatewayPrepareResponse {
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
  diagnostics: GatewaySessionDiagnostics;
}

export interface GatewayActivateResponse {
  prepared_session_id: string;
  binding_id: string;
  synapse_session_id: string;
  runtime_session_id: string;
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
  diagnostics: GatewaySessionDiagnostics;
}

const configuredGatewayBaseUrl = getConfiguredGatewayBaseUrl();

async function ensureOk(response: Response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response;
}

function getConfiguredGatewayBaseUrl(): URL | null {
  const raw = import.meta.env.VITE_GATEWAY_BASE_URL?.trim();
  if (!raw) {
    return null;
  }
  return new URL(raw, window.location.origin);
}

function withTrailingSlash(value: string): string {
  return value.endsWith("/") ? value : `${value}/`;
}

function normalizePath(path: string): string {
  return path.replace(/^\/+/, "");
}

function buildGatewayHttpUrl(path: string): string {
  if (configuredGatewayBaseUrl === null) {
    return path;
  }
  return new URL(normalizePath(path), withTrailingSlash(configuredGatewayBaseUrl.href)).toString();
}

export async function getGatewayConfig(): Promise<GatewayConfig> {
  const response = await fetch(buildGatewayHttpUrl("/gateway/agora-convoai/config"));
  return (await ensureOk(response)).json();
}

export async function prepareGatewaySession(
  payload: GatewaySessionPrepareRequest = {},
): Promise<GatewayPrepareResponse> {
  const response = await fetch(buildGatewayHttpUrl("/gateway/agora-convoai/sessions/prepare"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await ensureOk(response)).json();
}

export async function activateGatewaySession(
  payload: GatewaySessionActivateRequest,
): Promise<GatewayActivateResponse> {
  const response = await fetch(buildGatewayHttpUrl("/gateway/agora-convoai/sessions/activate"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await ensureOk(response)).json();
}

export async function stopGatewaySession(bindingId: string): Promise<void> {
  const response = await fetch(buildGatewayHttpUrl("/gateway/agora-convoai/sessions/stop"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ binding_id: bindingId }),
  });
  await ensureOk(response);
}

export function stopGatewaySessionBeacon(bindingId: string): boolean {
  if (typeof navigator === "undefined" || typeof navigator.sendBeacon !== "function") {
    return false;
  }
  const payload = JSON.stringify({ binding_id: bindingId });
  return navigator.sendBeacon(
    buildGatewayHttpUrl("/gateway/agora-convoai/sessions/stop"),
    new Blob([payload], { type: "application/json" }),
  );
}
