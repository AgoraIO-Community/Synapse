import type {
  CommandResponse,
  SessionSnapshot,
  TaskCommandType,
  MessageResponse,
  SessionResponse,
} from "./types";

const JSON_HEADERS = {
  "Content-Type": "application/json",
};

async function ensureOk(response: Response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response;
}

export async function createSession(): Promise<SessionResponse> {
  const response = await fetch("/sessions", {
    method: "POST",
  });
  return (await ensureOk(response)).json();
}

export async function sendMessage(
  sessionId: string,
  text: string,
): Promise<MessageResponse> {
  const response = await fetch(`/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ text }),
  });
  return (await ensureOk(response)).json();
}

export async function sendCommand(
  sessionId: string,
  commandType: TaskCommandType,
  targetTaskId: string,
): Promise<CommandResponse> {
  const response = await fetch(`/sessions/${sessionId}/commands`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      command_type: commandType,
      task_id: targetTaskId,
    }),
  });
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
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${window.location.host}${path}`);

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
    onMessage: (event: SessionSnapshot) => void;
    onClose: () => void;
    onError: () => void;
  },
): WebSocket {
  return openSocket<SessionSnapshot>(`/sessions/${sessionId}/stream`, handlers);
}
