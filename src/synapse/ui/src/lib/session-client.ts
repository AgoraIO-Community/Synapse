import type {
  ConversationSnapshot,
  DiagnosticTimelineResponse,
  SessionResponse,
  SessionSnapshot,
  SessionStreamEvent,
  TaskCommandType,
} from "../types";

const configuredApiBaseUrl = getConfiguredApiBaseUrl();

async function ensureOk(response: Response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response;
}

function getConfiguredApiBaseUrl(): URL | null {
  const raw = import.meta.env.VITE_API_BASE_URL?.trim();
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

function buildHttpUrl(path: string): string {
  if (configuredApiBaseUrl === null) {
    return path;
  }
  return new URL(normalizePath(path), withTrailingSlash(configuredApiBaseUrl.href)).toString();
}

function buildWebSocketUrl(path: string): string {
  if (configuredApiBaseUrl === null) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${path}`;
  }

  const socketUrl = new URL(normalizePath(path), withTrailingSlash(configuredApiBaseUrl.href));
  if (socketUrl.protocol === "https:") {
    socketUrl.protocol = "wss:";
  } else if (socketUrl.protocol === "http:") {
    socketUrl.protocol = "ws:";
  }
  return socketUrl.toString();
}

export async function createSession(): Promise<SessionResponse> {
  const response = await fetch(buildHttpUrl("/sessions"), {
    method: "POST",
  });
  return (await ensureOk(response)).json();
}

export async function getSessionSnapshot(sessionId: string): Promise<SessionSnapshot> {
  const response = await fetch(buildHttpUrl(`/sessions/${sessionId}`));
  return (await ensureOk(response)).json();
}

export async function getConversationSnapshot(sessionId: string): Promise<ConversationSnapshot> {
  const response = await fetch(buildHttpUrl(`/sessions/${sessionId}/conversation`));
  return (await ensureOk(response)).json();
}

export async function getDiagnosticTimeline(
  sessionId: string,
  params: {
    afterSequence?: number;
    taskId?: string;
    runId?: string;
    executionSessionId?: string;
    requestId?: string;
    eventPrefix?: string;
    minLevel?: string;
    limit?: number;
  } = {},
): Promise<DiagnosticTimelineResponse> {
  const query = new URLSearchParams();
  if (params.afterSequence !== undefined) {
    query.set("after_sequence", String(params.afterSequence));
  }
  if (params.taskId) {
    query.set("task_id", params.taskId);
  }
  if (params.runId) {
    query.set("run_id", params.runId);
  }
  if (params.executionSessionId) {
    query.set("execution_session_id", params.executionSessionId);
  }
  if (params.requestId) {
    query.set("request_id", params.requestId);
  }
  if (params.eventPrefix) {
    query.set("event_prefix", params.eventPrefix);
  }
  if (params.minLevel) {
    query.set("min_level", params.minLevel);
  }
  if (params.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await fetch(buildHttpUrl(`/sessions/${sessionId}/diagnostics/timeline${suffix}`));
  return (await ensureOk(response)).json();
}

function openSocket<TEvent>(
  path: string,
  handlers: {
    onOpen: () => void;
    onMessage: (event: TEvent) => void;
    onClose: () => void;
    onError: () => void;
  },
): WebSocket {
  const socket = new WebSocket(buildWebSocketUrl(path));

  socket.addEventListener("open", handlers.onOpen);
  socket.addEventListener("close", handlers.onClose);
  socket.addEventListener("error", handlers.onError);
  socket.addEventListener("message", (messageEvent) => {
    const parsed = JSON.parse(messageEvent.data) as TEvent;
    handlers.onMessage(parsed);
  });

  return socket;
}

export function openSessionStream(
  sessionId: string,
  handlers: {
    onOpen: () => void;
    onMessage: (event: SessionStreamEvent) => void;
    onClose: () => void;
    onError: () => void;
  },
): WebSocket {
  return openSocket<SessionStreamEvent>(`/sessions/${sessionId}/stream`, handlers);
}

export function sendSocketMessage(socket: WebSocket, requestId: string, text: string) {
  socket.send(
    JSON.stringify({
      type: "send_message",
      request_id: requestId,
      text,
    }),
  );
}

export function sendSocketCommand(
  socket: WebSocket,
  requestId: string,
  commandType: TaskCommandType,
  targetTaskId: string,
) {
  socket.send(
    JSON.stringify({
      type: "send_command",
      request_id: requestId,
      command_type: commandType,
      task_id: targetTaskId,
    }),
  );
}


// --- Persona API ---

export interface PersonaCreatePayload {
  name: string;
  avatar?: string;
  base_prompt?: string;
}

export interface PersonaUpdatePayload {
  name?: string;
  avatar?: string;
  base_prompt?: string;
}

export async function listPersonas(sessionId: string) {
  const response = await fetch(buildHttpUrl(`/sessions/${sessionId}/personas`));
  return (await ensureOk(response)).json();
}

export async function createPersona(sessionId: string, payload: PersonaCreatePayload) {
  const response = await fetch(buildHttpUrl(`/sessions/${sessionId}/personas`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await ensureOk(response)).json();
}

export async function updatePersona(
  sessionId: string,
  personaId: string,
  payload: PersonaUpdatePayload,
) {
  const response = await fetch(buildHttpUrl(`/sessions/${sessionId}/personas/${personaId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await ensureOk(response)).json();
}

export async function deletePersona(sessionId: string, personaId: string) {
  const response = await fetch(buildHttpUrl(`/sessions/${sessionId}/personas/${personaId}`), {
    method: "DELETE",
  });
  return (await ensureOk(response)).json();
}
