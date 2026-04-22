import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import App from "../App";
import type { ConversationSnapshot, SessionStreamEvent, SessionSnapshot } from "../types";

type StreamHandlers = {
  onOpen: () => void;
  onMessage: (event: SessionStreamEvent) => void;
  onClose: () => void;
  onError: () => void;
};

const streamState = {
  handlersBySession: new Map<string, StreamHandlers>(),
  socketsBySession: new Map<
    string,
    {
      close: ReturnType<typeof vi.fn>;
      send: ReturnType<typeof vi.fn>;
    }
  >(),
  reset() {
    streamState.handlersBySession = new Map();
    streamState.socketsBySession = new Map();
  },
};

const agoraState = vi.hoisted(() => {
  const state = {
    voiceEvents: {} as Record<string, (...args: any[]) => void>,
    rtcClient: {
      on: vi.fn(),
      subscribe: vi.fn(async () => {}),
      join: vi.fn(async () => {}),
      publish: vi.fn(async () => {}),
      leave: vi.fn(async () => {}),
    },
    micTrack: {
      stop: vi.fn(),
      close: vi.fn(),
      setEnabled: vi.fn(async () => {}),
    },
    rtmClient: {
      login: vi.fn(async () => {}),
      subscribe: vi.fn(async () => {}),
      logout: vi.fn(async () => {}),
    },
    voiceAi: {
      on: vi.fn((event: string, callback: (...args: any[]) => void) => {
        state.voiceEvents[event] = callback;
      }),
      subscribeMessage: vi.fn(),
      unsubscribe: vi.fn(),
      destroy: vi.fn(),
    },
    reset() {
      state.voiceEvents = {};
      state.rtcClient.on.mockClear();
      state.rtcClient.subscribe.mockClear();
      state.rtcClient.join.mockClear();
      state.rtcClient.publish.mockClear();
      state.rtcClient.leave.mockClear();
      state.micTrack.stop.mockClear();
      state.micTrack.close.mockClear();
      state.micTrack.setEnabled.mockClear();
      state.rtmClient.login.mockClear();
      state.rtmClient.subscribe.mockClear();
      state.rtmClient.logout.mockClear();
      state.voiceAi.on.mockClear();
      state.voiceAi.subscribeMessage.mockClear();
      state.voiceAi.unsubscribe.mockClear();
      state.voiceAi.destroy.mockClear();
    },
  };
  return state;
});

const clientMock = vi.hoisted(() => ({
  createSession: vi.fn(),
  getSessionSnapshot: vi.fn(),
  getConversationSnapshot: vi.fn(),
  getSessionConfig: vi.fn(async () => ({ key: "communication_persona_prompt", value: "" })),
  putSessionConfig: vi.fn(
    async (_sessionId: string, _key: string, value: string) => ({
      key: "communication_persona_prompt",
      value,
    }),
  ),
  getDiagnosticTimeline: vi.fn(async () => ({ events: [] })),
  openSessionStream: vi.fn((sessionId: string, handlers: StreamHandlers) => {
    streamState.handlersBySession.set(sessionId, handlers);
    const socket = {
      readyState: WebSocket.OPEN,
      close: vi.fn(),
      send: vi.fn(),
    };
    streamState.socketsBySession.set(sessionId, socket);
    queueMicrotask(() => handlers.onOpen());
    return socket as unknown as WebSocket;
  }),
  sendSocketCommand: vi.fn(),
  sendSocketMessage: vi.fn(),
}));

const connectorMock = vi.hoisted(() => ({
  getConnectorConfig: vi.fn<
    () => Promise<{
      ready: boolean;
      service_base_url: string;
      defaults: Record<string, never>;
      missing_requirements: string[];
    }>
  >(async () => ({
    ready: true,
    service_base_url: "https://connectors.example.com",
    defaults: {},
    missing_requirements: [],
  })),
  prepareConnectorSession: vi.fn(async () => ({
    prepared_session_id: "prepared-1",
    app_id: "agora-app",
    channel_name: "voice-room",
    token: "voice-token",
    uid: 101,
    user_rtm_uid: "101-voice-room",
    agent: {
      uid: "9001",
    },
    agent_rtm_uid: "9001-voice-room",
    enable_string_uid: false,
    profile: "VOICE",
    display_name: "Synapse Tester",
    diagnostics: {
      convoai_area: "US",
      selected_url: "https://agora.example.com",
      runtime_session_id: null,
      asr_vendor: "deepgram",
      asr_credential_mode: "managed",
      asr_model: "nova-3",
      tts_vendor: "minimax",
      tts_credential_mode: "managed",
      tts_model: "speech_2_6_turbo",
      agent_uid: "9001",
      agent_rtm_uid: "9001-voice-room",
      rtc_uid: 101,
      rtm_user_id: "101-voice-room",
      enable_string_uid: false,
      enable_rtm: true,
      data_channel: "rtm",
      enable_metrics: true,
      enable_error_message: true,
    },
  })),
  activateConnectorSession: vi.fn(async () => ({
    prepared_session_id: "prepared-1",
    binding_id: "binding-1",
    synapse_session_id: "voice-session-1",
    runtime_session_id: "runtime-1",
    chat_completions_url: "https://connectors.example.com/chat",
    app_id: "agora-app",
    channel_name: "voice-room",
    token: "voice-token",
    uid: 101,
    user_rtm_uid: "101-voice-room",
    agent: {
      uid: "9001",
    },
    agent_rtm_uid: "9001-voice-room",
    enable_string_uid: false,
    profile: "VOICE",
    display_name: "Synapse Tester",
    diagnostics: {
      convoai_area: "US",
      selected_url: "https://agora.example.com",
      runtime_session_id: "runtime-1",
      asr_vendor: "deepgram",
      asr_credential_mode: "managed",
      asr_model: "nova-3",
      tts_vendor: "minimax",
      tts_credential_mode: "managed",
      tts_model: "speech_2_6_turbo",
      agent_uid: "9001",
      agent_rtm_uid: "9001-voice-room",
      rtc_uid: 101,
      rtm_user_id: "101-voice-room",
      enable_string_uid: false,
      enable_rtm: true,
      data_channel: "rtm",
      enable_metrics: true,
      enable_error_message: true,
    },
  })),
  stopConnectorSession: vi.fn(async () => {}),
  stopConnectorSessionBeacon: vi.fn(() => true),
}));

type SessionSnapshotOverrides = Partial<Omit<SessionSnapshot, "session_id" | "personas">> & {
  personas?: SessionSnapshot["personas"];
};

vi.mock("../lib/session-client", () => clientMock);
vi.mock("../lib/connector-client", () => connectorMock);
vi.mock("agora-rtc-sdk-ng", () => ({
  default: {
    createClient: vi.fn(() => agoraState.rtcClient),
    createMicrophoneAudioTrack: vi.fn(async () => agoraState.micTrack),
  },
}));
vi.mock("agora-rtm", () => ({
  default: {
    RTM: vi.fn().mockImplementation(function MockRTM() {
      return agoraState.rtmClient;
    }),
  },
}));
vi.mock("agora-agent-client-toolkit", () => ({
  AgoraVoiceAI: {
    init: vi.fn(async () => agoraState.voiceAi),
  },
  AgoraVoiceAIEvents: {
    TRANSCRIPT_UPDATED: "TRANSCRIPT_UPDATED",
    AGENT_STATE_CHANGED: "AGENT_STATE_CHANGED",
    AGENT_ERROR: "AGENT_ERROR",
    MESSAGE_ERROR: "MESSAGE_ERROR",
    AGENT_INTERRUPTED: "AGENT_INTERRUPTED",
    DEBUG_LOG: "DEBUG_LOG",
  },
  TranscriptHelperMode: {
    AUTO: "AUTO",
  },
}));

function makeSnapshot(sessionId: string, overrides: SessionSnapshotOverrides = {}): SessionSnapshot {
  const personas = overrides.personas ?? [];
  return {
    session_id: sessionId,
    tasks: [],
    execution_sessions: [],
    execution_runs: [],
    execution_modes: [],
    bindings: [],
    summaries: [],
    notification_candidates: [],
    interaction_requests: [],
    attention_items: [],
    executor_capabilities: [],
    communication_persona_prompt: "",
    ...overrides,
    personas,
  };
}

function emit(sessionId: string, event: SessionStreamEvent) {
  const handlers = streamState.handlersBySession.get(sessionId);
  if (!handlers) {
    throw new Error(`stream handlers not ready for ${sessionId}`);
  }
  handlers.onMessage(event);
}

describe("App shell", () => {
  let textSessionCounter = 0;

  beforeEach(() => {
    streamState.reset();
    vi.clearAllMocks();
    agoraState.reset();
    textSessionCounter = 0;
    Object.defineProperty(globalThis.navigator, "sendBeacon", {
      configurable: true,
      value: vi.fn(() => true),
    });

    clientMock.createSession.mockImplementation(async () => {
      textSessionCounter += 1;
      return { session_id: `text-session-${textSessionCounter}` };
    });
    clientMock.getSessionSnapshot.mockImplementation(async (sessionId: string) =>
      makeSnapshot(sessionId),
    );
    clientMock.getConversationSnapshot.mockImplementation(async (sessionId: string) => ({
      session_id: sessionId,
      conversation_history: [],
    }));
    clientMock.getSessionConfig.mockImplementation(
      async () => ({ key: "communication_persona_prompt", value: "" }),
    );
    clientMock.putSessionConfig.mockImplementation(
      async (...args: [string, string, string]) => ({
        key: "communication_persona_prompt",
        value: args[2],
      }),
    );
    connectorMock.getConnectorConfig.mockResolvedValue({
      ready: true,
      service_base_url: "https://connectors.example.com",
      defaults: {},
      missing_requirements: [],
    });

    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("min-width: 1280px"),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  function renderApp() {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    );
  }

  it("boots into voice mode with the vertical-attached switch and idle voice controls", async () => {
    renderApp();

    expect(await screen.findByTestId("mode-switch-shell")).toBeInTheDocument();
    expect(screen.getByTestId("mode-switch-text")).toBeInTheDocument();
    expect(screen.getByTestId("mode-switch-voice")).toBeInTheDocument();
    expect(await screen.findByText("Talk to NewBro live.")).toBeInTheDocument();
    expect(await screen.findByTestId("voice-mode-transcript-feed")).toBeInTheDocument();
    expect(screen.queryByTestId("conversation-composer-shell")).not.toBeInTheDocument();
    expect(await screen.findByTestId("voice-session-start")).toBeInTheDocument();
    expect(streamState.handlersBySession.size).toBe(0);
    expect(connectorMock.prepareConnectorSession).not.toHaveBeenCalled();
  });

  it("switches to text mode and shows the text composer plus starter prompts", async () => {
    renderApp();

    fireEvent.click(await screen.findByTestId("mode-switch-text"));

    expect(await screen.findByTestId("conversation-composer-shell")).toBeInTheDocument();
    expect(await screen.findByText("Write a clear instruction.")).toBeInTheDocument();
    expect(screen.getByText("Starter prompts")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Draft a clear release note for the current sprint." })).toBeInTheDocument();
  });

  it("starts voice mode on demand and binds the workbench stream to the voice session", async () => {
    renderApp();

    fireEvent.click(await screen.findByTestId("mode-switch-text"));
    await waitFor(() => expect(streamState.handlersBySession.has("text-session-1")).toBe(true));
    fireEvent.click(await screen.findByTestId("mode-switch-voice"));
    expect(streamState.handlersBySession.has("voice-session-1")).toBe(false);
    fireEvent.click(await screen.findByTestId("voice-session-start"));

    await waitFor(() => expect(connectorMock.prepareConnectorSession).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(connectorMock.activateConnectorSession).toHaveBeenCalledWith({
        prepared_session_id: "prepared-1",
      }),
    );
    await waitFor(() => expect(streamState.handlersBySession.has("voice-session-1")).toBe(true));
    expect(screen.queryByTestId("conversation-composer-shell")).not.toBeInTheDocument();
    expect(await screen.findByTestId("voice-mode-transcript-feed")).toBeInTheDocument();
    expect(screen.getByText("Voice mode")).toBeInTheDocument();

    await act(async () => {
      emit(
        "voice-session-1",
        {
          type: "snapshot",
          sequence: 1,
          snapshot: makeSnapshot("voice-session-1", {
            tasks: [
              {
                task_id: "task-voice-1",
                root_task_id: "task-voice-1",
                parent_task_id: null,
                title: "Voice follow-up task",
                goal: "Track the live voice-mode task",
                status: "running",
                priority: 1,
                interruptible: true,
                requires_confirmation: false,
                preferred_executor: "mock",
                session_affinity: null,
                task_revision: 1,
                latest_instruction: "Follow up on the spoken request",
                metadata: {},
              },
            ],
          }),
        } as SessionStreamEvent,
      );
    });

    expect((await screen.findAllByText("Voice follow-up task")).length).toBeGreaterThan(0);
  });

  it("keeps rendering transcript updates after the greeting in voice mode", async () => {
    renderApp();

    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(streamState.handlersBySession.has("voice-session-1")).toBe(true));

    await act(async () => {
      agoraState.voiceEvents.TRANSCRIPT_UPDATED?.([
        { turn_id: "turn-1", uid: "9001", text: "Hello. How can I help you today?", status: "final" },
      ]);
    });

    expect(await screen.findByText("Hello. How can I help you today?")).toBeInTheDocument();
    expect(screen.getByText("NewBro")).toBeInTheDocument();
    expect(screen.queryByText("UID 9001")).not.toBeInTheDocument();
    expect(screen.queryByText("final")).not.toBeInTheDocument();

    await act(async () => {
      agoraState.voiceEvents.TRANSCRIPT_UPDATED?.([
        { turn_id: "turn-1", uid: "9001", text: "Hello. How can I help you today?", status: "final" },
        { turn_id: "turn-2", uid: "101", text: "Please create a follow-up task.", status: "final" },
        { turn_id: "turn-3", uid: "9001", text: "I am creating that task now.", status: "final" },
      ]);
    });

    expect(await screen.findByText("Please create a follow-up task.")).toBeInTheDocument();
    expect(screen.getByText("I am creating that task now.")).toBeInTheDocument();
    expect(screen.getByText("Me")).toBeInTheDocument();
    expect(screen.queryByText("UID 101")).not.toBeInTheDocument();
  });

  it("stops the active voice session back to idle voice mode", async () => {
    renderApp();

    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(streamState.handlersBySession.has("voice-session-1")).toBe(true));
    fireEvent.click(screen.getByTestId("voice-session-stop"));

    await waitFor(() => expect(connectorMock.stopConnectorSession).toHaveBeenCalledWith("binding-1"));
    expect(screen.queryByTestId("conversation-composer-shell")).not.toBeInTheDocument();
    expect(await screen.findByTestId("voice-session-start")).toBeInTheDocument();
    expect(screen.getByText(/no live session is running yet/i)).toBeInTheDocument();
  });

  it("keeps the binding available so a failed stop can be retried", async () => {
    connectorMock.stopConnectorSession
      .mockRejectedValueOnce(new Error("temporary stop failure"))
      .mockResolvedValueOnce(undefined);

    renderApp();

    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(streamState.handlersBySession.has("voice-session-1")).toBe(true));
    fireEvent.click(screen.getByTestId("voice-session-stop"));

    expect((await screen.findAllByText("temporary stop failure")).length).toBeGreaterThan(0);
    expect(await screen.findByTestId("voice-session-retry-stop")).toBeInTheDocument();
    expect(streamState.handlersBySession.has("voice-session-1")).toBe(true);

    fireEvent.click(screen.getByTestId("voice-session-retry-stop"));

    await waitFor(() => expect(connectorMock.stopConnectorSession).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId("voice-session-start")).toBeInTheDocument();
  });

  it("mutes and unmutes the microphone while the voice session stays live", async () => {
    renderApp();

    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(streamState.handlersBySession.has("voice-session-1")).toBe(true));

    fireEvent.click(screen.getByTestId("voice-session-mic-toggle"));
    await waitFor(() => expect(agoraState.micTrack.setEnabled).toHaveBeenCalledWith(false));
    expect(await screen.findByText("Muted")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("voice-session-mic-toggle"));
    await waitFor(() => expect(agoraState.micTrack.setEnabled).toHaveBeenCalledWith(true));
    expect(await screen.findByText("Live")).toBeInTheDocument();
  });

  it("switches from active voice mode to a fresh text session", async () => {
    renderApp();

    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(streamState.handlersBySession.has("voice-session-1")).toBe(true));
    fireEvent.click(screen.getByTestId("mode-switch-text"));

    await waitFor(() => expect(connectorMock.stopConnectorSession).toHaveBeenCalledWith("binding-1"));
    await waitFor(() => expect(clientMock.createSession).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(streamState.handlersBySession.has("text-session-1")).toBe(true));
    expect(await screen.findByTestId("conversation-composer-shell")).toBeInTheDocument();
  });

  it("shows a voice-mode startup error when connector config is incomplete", async () => {
    connectorMock.getConnectorConfig.mockImplementationOnce(async () => ({
      ready: false,
      service_base_url: "https://connectors.example.com",
      defaults: {},
      missing_requirements: ["connectors.agora-convoai.app_id"] as string[],
    }));

    renderApp();
    fireEvent.click(await screen.findByTestId("voice-session-start"));

    expect(await screen.findByText(/connectors\.agora-convoai\.app_id/)).toBeInTheDocument();
  });

  it("signals the connector stop endpoint on pagehide while a voice session is active", async () => {
    const { unmount } = renderApp();

    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(streamState.handlersBySession.has("voice-session-1")).toBe(true));

    unmount();

    expect(connectorMock.stopConnectorSessionBeacon).toHaveBeenCalledTimes(1);
    expect(connectorMock.stopConnectorSessionBeacon).toHaveBeenCalledWith("binding-1");
  });

  it("sends text-mode composer messages through the active text session websocket", async () => {
    renderApp();

    fireEvent.click(await screen.findByTestId("mode-switch-text"));
    await waitFor(() => expect(streamState.handlersBySession.has("text-session-1")).toBe(true));

    const input = screen.getByPlaceholderText("Issue a system directive...");
    fireEvent.change(input, { target: { value: "Review the active tasks" } });
    fireEvent.click(screen.getByTestId("conversation-composer-send"));

    expect(clientMock.sendSocketMessage).toHaveBeenCalledWith(
      expect.anything(),
      expect.any(String),
      "Review the active tasks",
    );
  });
});
