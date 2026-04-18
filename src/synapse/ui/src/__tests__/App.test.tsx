import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import App from "../App";
import type { ConversationSnapshot, SessionResponse, SessionStreamEvent, SessionSnapshot } from "../types";

type StreamHandlers = {
  onOpen: () => void;
  onMessage: (event: SessionStreamEvent) => void;
  onClose: () => void;
  onError: () => void;
};

const streamState: {
  handlers: StreamHandlers | null;
} = {
  handlers: null,
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
  createSession: vi.fn<() => Promise<SessionResponse>>(async () => ({ session_id: "session-test" })),
  getSessionSnapshot: vi.fn<() => Promise<SessionSnapshot>>(async () => makeSnapshot()),
  getConversationSnapshot: vi.fn<() => Promise<ConversationSnapshot>>(async () => ({
    session_id: "session-test",
    conversation_history: [],
  })),
  getDiagnosticTimeline: vi.fn(async () => ({ events: [] })),
  openSessionStream: vi.fn((_sessionId: string, handlers: StreamHandlers) => {
    streamState.handlers = handlers;
    queueMicrotask(() => handlers.onOpen());
    return {
      readyState: WebSocket.OPEN,
      close: vi.fn(),
      send: vi.fn(),
    } as unknown as WebSocket;
  }),
  sendSocketCommand: vi.fn(),
  sendSocketMessage: vi.fn(),
}));

const gatewayMock = vi.hoisted(() => ({
  getGatewayConfig: vi.fn<
    () => Promise<{
      ready: boolean;
      service_base_url: string;
      defaults: Record<string, never>;
      missing_requirements: string[];
    }>
  >(async () => ({
    ready: true,
    service_base_url: "https://gateway.example.com",
    defaults: {},
    missing_requirements: [],
  })),
  prepareGatewaySession: vi.fn(async () => ({
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
  activateGatewaySession: vi.fn(async () => ({
    prepared_session_id: "prepared-1",
    binding_id: "binding-1",
    synapse_session_id: "voice-session-1",
    runtime_session_id: "runtime-1",
    chat_completions_url: "https://gateway.example.com/chat",
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
  stopGatewaySession: vi.fn(async () => {}),
}));

vi.mock("../lib/session-client", () => clientMock);
vi.mock("../lib/gateway-client", () => gatewayMock);
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
  },
  TranscriptHelperMode: {
    TEXT: "TEXT",
  },
}));

function makeSnapshot(overrides: Partial<SessionSnapshot> = {}): SessionSnapshot {
  return {
    session_id: "session-test",
    tasks: [],
    execution_sessions: [],
    execution_runs: [],
    execution_modes: [],
    bindings: [],
    summaries: [],
    notification_candidates: [],
    ...overrides,
  };
}

function emit(event: SessionStreamEvent) {
  if (!streamState.handlers) {
    throw new Error("stream handlers not ready");
  }
  streamState.handlers.onMessage(event);
}

describe("App shell", () => {
  beforeEach(() => {
    streamState.handlers = null;
    vi.clearAllMocks();
    agoraState.reset();
    gatewayMock.getGatewayConfig.mockResolvedValue({
      ready: true,
      service_base_url: "https://gateway.example.com",
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

  it("renders a chat-first conversation and workbench shell", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Conversation" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Workbench" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active Tasks" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Debug" })).toBeInTheDocument();
    expect(screen.queryByText("Execution visibility")).not.toBeInTheDocument();
    expect(screen.getByTestId("workbench-queue-stack")).toBeInTheDocument();
    expect(screen.queryByText((content) => content.includes("tracked"))).not.toBeInTheDocument();
  });

  it("renders the atmospheric split shell scaffolding around the conversation and workbench panes", async () => {
    renderApp();

    expect(await screen.findByTestId("workspace-atmosphere")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-left-pane")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-right-pane")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-split-seam")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("workspace-right-pane").querySelector('[aria-hidden="true"]'),
    ).not.toBeInTheDocument();
  });

  it("renders the left composer as a monolith capsule with waveform controls", async () => {
    renderApp();

    expect(await screen.findByTestId("conversation-composer-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("conversation-composer-text-mode")).not.toBeInTheDocument();
    expect(screen.queryByTestId("conversation-composer-waveform")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Issue a system directive...").tagName).toBe("INPUT");
  });

  it("renders the composer send button as a compact circular control", async () => {
    renderApp();

    const sendButton = await screen.findByTestId("conversation-composer-send");
    expect(sendButton).toBeInTheDocument();
    expect(sendButton.className).not.toContain("bg-[linear-gradient(135deg,#12907a_0%,#0b5748_100%)]");
    expect(screen.queryByText("Send")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Send")).toBeInTheDocument();
  });

  it("keeps the left pane visually minimal by removing the old top descriptive clutter", async () => {
    renderApp();

    expect(screen.queryByText("Chat-first runtime control with a live execution workbench.")).not.toBeInTheDocument();
    expect(screen.queryByText("connecting")).not.toBeInTheDocument();
    expect(screen.getByTestId("workspace-left-pane").className).toContain("min-w-0");
  });

  it("renders the parallel voice accessory near the composer without replacing the text session flow", async () => {
    renderApp();

    expect(await screen.findByTestId("voice-accessory-shell")).toBeInTheDocument();
    expect(await screen.findByTestId("voice-accessory-start")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Issue a system directive...")).toBeInTheDocument();
    expect(screen.getByText("Voice stays parallel to the main workbench session.")).toBeInTheDocument();
  });

  it("shows a gateway config error in the voice accessory when the Agora gateway is not ready", async () => {
    gatewayMock.getGatewayConfig.mockImplementationOnce(async () => ({
      ready: false,
      service_base_url: "https://gateway.example.com",
      defaults: {},
      missing_requirements: ["gateways.agora-convoai.app_id"] as string[],
    }));

    renderApp();

    expect(await screen.findByTestId("voice-accessory-error")).toHaveTextContent(
      "gateways.agora-convoai.app_id",
    );
    expect(screen.getByTestId("voice-accessory-start")).toBeDisabled();
  });

  it("starts and stops the compact voice accessory session through the gateway lifecycle", async () => {
    renderApp();

    const startButton = await screen.findByTestId("voice-accessory-start");
    await waitFor(() => expect(startButton).toBeEnabled());

    fireEvent.click(startButton);

    await waitFor(() => expect(gatewayMock.prepareGatewaySession).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(gatewayMock.activateGatewaySession).toHaveBeenCalledWith({
        prepared_session_id: "prepared-1",
      }),
    );
    expect(await screen.findByText("Voice live")).toBeInTheDocument();
    expect(agoraState.voiceAi.subscribeMessage).toHaveBeenCalledWith("voice-room");

    await act(async () => {
      agoraState.voiceEvents.TRANSCRIPT_UPDATED?.([
        { turn_id: "turn-1", uid: "101", text: "Hello from voice mode", status: "final" },
      ]);
    });

    expect(await screen.findByText("Hello from voice mode")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("voice-accessory-stop"));

    await waitFor(() => expect(gatewayMock.stopGatewaySession).toHaveBeenCalledWith("binding-1"));
    expect(agoraState.voiceAi.unsubscribe).toHaveBeenCalled();
    expect(agoraState.rtcClient.leave).toHaveBeenCalled();
  });

  it("shows task update cards in the conversation timeline for important task events", async () => {
    renderApp();

    await waitFor(() => expect(streamState.handlers).not.toBeNull());

    await act(async () => {
      emit({
        type: "snapshot",
        sequence: 1,
        snapshot: makeSnapshot({
          tasks: [
            {
              task_id: "task-1",
              root_task_id: "task-1",
              parent_task_id: null,
              title: "Draft release note",
              goal: "Write and polish the release note",
              status: "completed",
              priority: 1,
              interruptible: true,
              requires_confirmation: false,
              preferred_executor: null,
              session_affinity: null,
              task_revision: 2,
              latest_instruction: "Draft the release note",
              metadata: {},
            },
          ],
          summaries: [
            {
              task_id: "task-1",
              operational_summary: "Release note drafted.",
              conversational_summary: "The release note is ready for review.",
              latest_user_visible_status: "Completed",
              needs_user_input: false,
            },
          ],
        }),
      });
    });

    expect(await screen.findByText("Task update")).toBeInTheDocument();
    expect(screen.getAllByText("Draft release note").length).toBeGreaterThan(0);
    expect(screen.getAllByText("The release note is ready for review.").length).toBeGreaterThan(0);
  });

  it("anchors completed task updates after the assistant message that affected the task", async () => {
    renderApp();

    await waitFor(() => expect(streamState.handlers).not.toBeNull());

    await act(async () => {
      emit({
        type: "assistant_response_completed",
        sequence: 1,
        request_id: "req-1",
        message_id: "msg-assistant-2",
        reply_text: "I created the reminder for you.",
        conversational_act: "inform",
        affected_task_ids: ["task-2"],
      });

      emit({
        type: "snapshot",
        sequence: 2,
        snapshot: makeSnapshot({
          tasks: [
            {
              task_id: "task-2",
              root_task_id: "task-2",
              parent_task_id: null,
              title: "Reminder: check status in 5 minutes",
              goal: "Create a simulated reminder",
              status: "completed",
              priority: 1,
              interruptible: true,
              requires_confirmation: false,
              preferred_executor: "mock",
              session_affinity: null,
              task_revision: 1,
              latest_instruction: "Create the reminder",
              metadata: {},
            },
          ],
          summaries: [
            {
              task_id: "task-2",
              operational_summary: "Reminder created.",
              conversational_summary: "Completed: Reminder: check status in 5 minutes",
              latest_user_visible_status: "Completed",
              needs_user_input: false,
            },
          ],
        }),
      });
    });

    const assistantMessage = await screen.findByText("I created the reminder for you.");
    const taskUpdateCard = await screen.findByText("Task update");
    const taskUpdate = within(taskUpdateCard.closest("button")!).getByText(
      "Reminder: check status in 5 minutes",
    );

    expect(
      assistantMessage.compareDocumentPosition(taskUpdate) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("does not open the mobile workbench drawer when clicking a task update on desktop", async () => {
    renderApp();

    await waitFor(() => expect(streamState.handlers).not.toBeNull());

    await act(async () => {
      emit({
        type: "snapshot",
        sequence: 1,
        snapshot: makeSnapshot({
          tasks: [
            {
              task_id: "task-3",
              root_task_id: "task-3",
              parent_task_id: null,
              title: "Review deployment summary",
              goal: "Check the deployment summary",
              status: "completed",
              priority: 1,
              interruptible: true,
              requires_confirmation: false,
              preferred_executor: null,
              session_affinity: null,
              task_revision: 1,
              latest_instruction: "Review the summary",
              metadata: {},
            },
          ],
          summaries: [
            {
              task_id: "task-3",
              operational_summary: "Summary reviewed.",
              conversational_summary: "The deployment summary is ready.",
              latest_user_visible_status: "Completed",
              needs_user_input: false,
            },
          ],
        }),
      });
    });

    const taskUpdate = await screen.findByText("Task update");
    fireEvent.click(taskUpdate.closest("button")!);

    expect(
      screen.queryByText("Task queue, details, and debug surfaces for the active session."),
    ).not.toBeInTheDocument();
  });

  it("renders a padded mobile workbench shell when the drawer is opened on mobile", async () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("max-width: 1279px"),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as typeof window.matchMedia;

    renderApp();

    fireEvent.click(await screen.findByText("Open workbench"));

    expect(await screen.findByTestId("mobile-workbench-shell")).toBeInTheDocument();
  });

  it("shows the empty-state starter surface only before the first conversation turn", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Start with a clear instruction." })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Draft a clear release note for the current sprint." })).toBeInTheDocument();
  });

  it("hides the empty-state starter surface once the conversation has content", async () => {
    clientMock.getConversationSnapshot.mockImplementationOnce(
      async () =>
        ({
          session_id: "session-test",
          conversation_history: [
            {
              role: "user",
              text: "Help me review the release note.",
              message_id: "msg-user-1",
            },
            {
              role: "assistant",
              text: "I can review that.",
              message_id: "msg-assistant-1",
            },
          ],
        }) as ConversationSnapshot,
    );

    renderApp();

    expect(await screen.findByText("Help me review the release note.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Start with a clear instruction." })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Draft a clear release note for the current sprint." }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("You")).not.toBeInTheDocument();
    expect(screen.queryByText("Assistant response")).not.toBeInTheDocument();
  });
});
