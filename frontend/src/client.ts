import type {
  ConversationSnapshot,
  DebugSnapshot,
  SessionStreamEvent,
  TaskCommandType,
  SessionResponse,
  SessionSnapshot,
} from "./types";

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

export async function getSessionSnapshot(sessionId: string): Promise<SessionSnapshot> {
  const response = await fetch(`/sessions/${sessionId}`);
  return (await ensureOk(response)).json();
}

export async function getConversationSnapshot(sessionId: string): Promise<ConversationSnapshot> {
  const response = await fetch(`/sessions/${sessionId}/conversation`);
  return (await ensureOk(response)).json();
}

export async function getDebugSnapshot(sessionId: string): Promise<DebugSnapshot> {
  const response = await fetch(`/sessions/${sessionId}/debug`);
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
