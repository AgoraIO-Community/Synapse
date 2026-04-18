import { afterEach, describe, expect, it, vi } from "vitest";

class MockWebSocket {
  static readonly OPEN = 1;
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readonly readyState = MockWebSocket.OPEN;
  readonly addEventListener = vi.fn();
  readonly close = vi.fn();
  readonly send = vi.fn();

  constructor(url: string | URL) {
    this.url = String(url);
    MockWebSocket.instances.push(this);
  }
}

function okJsonResponse(payload: object): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("session-client transport base URL handling", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    MockWebSocket.instances = [];
  });

  it("uses relative HTTP paths and the current origin websocket URL by default", async () => {
    const fetchMock = vi.fn(async () => okJsonResponse({ session_id: "session-1" }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("WebSocket", MockWebSocket);

    const client = await import("./session-client");

    await client.createSession();
    client.openSessionStream("session-1", {
      onOpen: vi.fn(),
      onMessage: vi.fn(),
      onClose: vi.fn(),
      onError: vi.fn(),
    });

    expect(fetchMock).toHaveBeenCalledWith("/sessions", {
      method: "POST",
    });
    expect(MockWebSocket.instances[0]?.url).toBe(
      `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/sessions/session-1/stream`,
    );
  });

  it("uses the configured HTTPS base URL for fetches and WSS for websocket streams", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    const fetchMock = vi.fn(async () => okJsonResponse({ session_id: "session-1" }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("WebSocket", MockWebSocket);

    const client = await import("./session-client");

    await client.createSession();
    client.openSessionStream("session-1", {
      onOpen: vi.fn(),
      onMessage: vi.fn(),
      onClose: vi.fn(),
      onError: vi.fn(),
    });

    expect(fetchMock).toHaveBeenCalledWith("https://api.example.com/sessions", {
      method: "POST",
    });
    expect(MockWebSocket.instances[0]?.url).toBe("wss://api.example.com/sessions/session-1/stream");
  });

  it("normalizes trailing slashes on the configured backend base URL", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com/runtime/");
    const fetchMock = vi.fn(async () =>
      okJsonResponse({
        session_id: "session-1",
        conversation_history: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = await import("./session-client");

    await client.getConversationSnapshot("session-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/runtime/sessions/session-1/conversation",
    );
  });
});
