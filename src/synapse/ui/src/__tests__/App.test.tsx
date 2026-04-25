import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { RouterProvider } from "@tanstack/react-router";
import React from "react";
import App from "../App";
import { buildBroCardModels } from "../components/newbro";
import { getRouter } from "../router";

const voiceHarness = vi.hoisted(() => {
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
      setMuted: vi.fn(async () => {}),
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
      state.micTrack.setMuted.mockClear();
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

const socketHarness = vi.hoisted(() => {
  const state = {
    handlers: null as
      | {
          onOpen: () => void;
          onMessage: (event: any) => void;
          onClose: () => void;
          onError: () => void;
        }
      | null,
    socket: {
      readyState: 1,
      close: vi.fn(),
    },
    emitMessage(event: any) {
      state.handlers?.onMessage(event);
    },
    reset() {
      state.handlers = null;
      state.socket.close.mockClear();
    },
  };
  return state;
});

const clientMock = vi.hoisted(() => ({
  createSession: vi.fn(),
  getSessionSnapshot: vi.fn(),
  getConversationSnapshot: vi.fn(async (sessionId: string) => ({
    session_id: sessionId,
    conversation_history: [],
  })),
  openSessionStream: vi.fn((_sessionId: string, handlers: any) => {
    socketHarness.handlers = handlers;
    return socketHarness.socket as any;
  }),
  sendSocketMessage: vi.fn(),
  createPersona: vi.fn(),
  updatePersona: vi.fn(),
  deletePersona: vi.fn(),
  listPersonas: vi.fn(async () => []),
  getSessionConfig: vi.fn(async () => ({ key: "communication_persona_prompt", value: "" })),
  putSessionConfig: vi.fn(async () => ({ key: "communication_persona_prompt", value: "" })),
  listExecutorNodes: vi.fn(async () => []),
  createExecutorNode: vi.fn(),
  updateExecutorNode: vi.fn(),
  rotateExecutorNodeCredentials: vi.fn(),
  revealExecutorNodeConnectCommand: vi.fn(),
  deleteExecutorNode: vi.fn(),
  buildExecutorRunCommand: vi.fn(() => "newbro executor run --base-url 'http://localhost:8000' --node-id 'node-1' --token 'token-1'"),
  submitDraftAsrTurn: vi.fn(async () => ({
    id: "draft-session-1",
    assigned_bro_id: "forge",
    status: "ready",
    current_draft: {
      title: "Draft landing page",
      goal: "Create a refined landing page concept.",
      canonical_instruction: "Design a polished landing page with a calm hero section.",
      constraints: ["Keep it concise"],
      acceptance_criteria: ["Shows a clear hero"],
      assumptions: ["Use existing brand tone"],
      missing_info: ["Confirm target audience"],
      last_update_summary: "Created a first draft from voice input.",
    },
  })),
}));

const connectorMock = vi.hoisted(() => ({
  getConnectorConfig: vi.fn(async () => ({
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
    synapse_session_id: "session-1",
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
  stopConnectorSessionBeacon: vi.fn(() => true),
  prepareSttSession: vi.fn(async () => ({
    prepared_stt_session_id: "prepared-stt-1",
    app_id: "agora-app",
    channel_name: "nbstt-session-bro-random",
    token: "stt-token",
    uid: 101,
    status: "prepared",
  })),
  startSttSession: vi.fn(async () => ({
    stt_session_id: "stt-1",
    app_id: "agora-app",
    channel_name: "nbstt-session-bro-random",
    token: "stt-token",
    uid: 101,
    pub_bot_uid: 100101,
    sub_bot_uid: 100101,
    agent_id: "agent-1",
    status: "started",
  })),
  heartbeatSttSession: vi.fn(async () => ({ status: "active" })),
  querySttSession: vi.fn(async () => ({
    stt_session_id: "stt-1",
    agent_id: "agent-1",
    status: "running",
    raw: {},
  })),
  leaveSttSession: vi.fn(async () => {}),
}));

const runtimeMock = vi.hoisted(() => ({
  loadAgoraBrowserStack: vi.fn(async () => ({
    AgoraRTC: {
      createClient: vi.fn(() => voiceHarness.rtcClient),
      createMicrophoneAudioTrack: vi.fn(async () => voiceHarness.micTrack),
    },
    AgoraRTM: {
      RTM: vi.fn().mockImplementation(function MockRTM() {
        return voiceHarness.rtmClient;
      }),
    },
    AgoraVoiceAI: {
      init: vi.fn(async () => voiceHarness.voiceAi),
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
  })),
  teardownVoiceSession: vi.fn(async () => {}),
}));

vi.mock("../lib/session-client", () => clientMock);
vi.mock("../lib/connector-client", () => connectorMock);
vi.mock("../lib/voice-runtime", () => runtimeMock);

describe("Newbro voice shell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    voiceHarness.reset();
    socketHarness.reset();
    window.history.replaceState({}, "", "/");
    clientMock.createSession.mockResolvedValue({ session_id: "session-1" });
    clientMock.getSessionSnapshot.mockImplementation(async (sessionId: string) => ({
      session_id: sessionId,
      tasks: [],
      execution_sessions: [],
      execution_runs: [],
      execution_modes: [],
      bindings: [],
      summaries: [],
      notification_candidates: [],
      personas: [],
      interaction_requests: [],
      attention_items: [],
      executor_capabilities: [],
      executor_nodes: [],
      communication_persona_prompt: "",
    }));
    clientMock.getConversationSnapshot.mockImplementation(async (sessionId: string) => ({
      session_id: sessionId,
      conversation_history: [],
    }));
  });

  it("boots into an explicit empty interaction-memory state", async () => {
    render(<App />);

    expect(await screen.findByText("Transcript will appear here.")).toBeInTheDocument();
    expect(screen.queryByTestId("voice-session-start")).not.toBeInTheDocument();
    expect(screen.queryByTestId("voice-session-stop")).not.toBeInTheDocument();
    expect(screen.queryByTestId("voice-session-mic-toggle")).not.toBeInTheDocument();
    expect(screen.queryByText("No transcript yet")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Start a live session to fill this memory with real transcript turns."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("No live session yet. Press Start in the top bar to begin voice interaction."),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Atlas")).toBeInTheDocument();

    await waitFor(() => expect(clientMock.createSession).toHaveBeenCalled());
    await waitFor(() => expect(clientMock.getSessionSnapshot).toHaveBeenCalledWith("session-1"));
    expect(window.location.search).toBe("?sid=session-1");
  });


  it("opens a Bro detail page when a Home card is clicked", async () => {
    render(<RouterProvider router={getRouter()} />);

    const atlasCard = await screen.findByTestId("bro-card-atlas");
    fireEvent.click(atlasCard);

    expect(await screen.findByText("Bro detail")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Atlas" })).toBeInTheDocument();
    expect(screen.getByText("Draft Brain")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/bros/atlas");
    expect(window.location.search).toBe("?sid=session-1");
  });

  it("renders a Bro detail route directly with the active shell session", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await waitFor(() => expect(clientMock.getSessionSnapshot).toHaveBeenCalledWith("session-existing"));
    expect(await screen.findByText("Bro detail")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Forge" })).toBeInTheDocument();
    expect(screen.getByText("No draft yet. Hold the mic to start shaping one.")).toBeInTheDocument();
    expect((await screen.findAllByText("Ready · mic off")).length).toBeGreaterThan(0);
  });

  it("publishes the Bro detail mic before muting it", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    expect((await screen.findAllByText("Ready · mic off")).length).toBeGreaterThan(0);
    expect(voiceHarness.rtcClient.publish).toHaveBeenCalledWith([voiceHarness.micTrack]);
    expect(voiceHarness.micTrack.setEnabled).not.toHaveBeenCalledWith(false);
    expect(voiceHarness.micTrack.setMuted).toHaveBeenCalledWith(true);
    expect(
      voiceHarness.rtcClient.publish.mock.invocationCallOrder[0],
    ).toBeLessThan(voiceHarness.micTrack.setMuted.mock.invocationCallOrder[0]);

    const micButton = screen.getByRole("button", { name: "Hold to Talk" });
    fireEvent.pointerDown(micButton, { pointerId: 1 });
    await waitFor(() => expect(voiceHarness.micTrack.setMuted).toHaveBeenCalledWith(false));
    expect(screen.queryByTestId("talking-bars")).not.toBeInTheDocument();
    fireEvent.blur(micButton);
    expect(voiceHarness.micTrack.setMuted).toHaveBeenLastCalledWith(false);
    fireEvent.pointerUp(micButton, { pointerId: 1 });
    await waitFor(() => expect(voiceHarness.micTrack.setMuted).toHaveBeenLastCalledWith(true));
  });

  it("renders Bro detail RTC debug events and unparsed stream messages", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findAllByText("Ready · mic off");
    const userJoinedHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "user-joined",
    )?.[1];
    const userPublishedHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "user-published",
    )?.[1];
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];

    await act(async () => {
      userJoinedHandler({ uid: 200101 });
      userPublishedHandler({ uid: 200101 }, "audio");
      transcriptHandler(200101, { nope: true });
    });

    expect(await screen.findByText(/Voice debug:/)).toHaveTextContent("unparsed stream-message");
    expect(screen.getByText(/Voice debug:/)).toHaveTextContent("object nope");
  });

  it("does not poll STT status from Bro detail", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findAllByText("Ready · mic off");

    expect(connectorMock.querySttSession).not.toHaveBeenCalled();
    expect(screen.getByText(/Voice debug:/)).not.toHaveTextContent("stt status");
  });

  it("renders final Bro detail transcript and returned draft content", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findAllByText("Ready · mic off");
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, {
        text: "Build a calm landing page",
        isFinal: true,
      });
    });

    expect((await screen.findAllByText("Build a calm landing page")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Draft landing page")).toBeInTheDocument();
    expect(screen.getByText("Create a refined landing page concept.")).toBeInTheDocument();
    expect(screen.getByText("Design a polished landing page with a calm hero section.")).toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).toHaveBeenCalledWith("session-existing", {
      raw_text: "Build a calm landing page",
      assigned_bro_id: "forge",
    });
  });

  it("renders non-final Bro detail transcript without updating draft", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findAllByText("Ready · mic off");
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, {
        result: {
          text: "Still listening to this sentence",
          isFinal: false,
        },
      });
    });

    expect(await screen.findByText("Still listening to this sentence")).toBeInTheDocument();
    expect(screen.getByText("Completed turns appear here when ASR marks a segment final.")).toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).not.toHaveBeenCalled();
  });

  it("hydrates interaction memory from durable history when the page opens", async () => {
    clientMock.getConversationSnapshot.mockResolvedValueOnce({
      session_id: "session-1",
      conversation_history: [
        { role: "assistant", text: "Hello from Synapse.", message_id: "msg-1" },
        { role: "user", text: "Please summarize the plan.", message_id: "msg-2" },
      ],
    } as any);

    render(<App />);

    expect(await screen.findByText("Hello from Synapse.")).toBeInTheDocument();
    expect(screen.getByText("Please summarize the plan.")).toBeInTheDocument();
    expect(screen.queryByText("Transcript will appear here.")).not.toBeInTheDocument();
    expect(screen.getByText("2 turns")).toBeInTheDocument();
  });

  it("resumes the shell session from the sid query parameter", async () => {
    window.history.replaceState({}, "", "/?sid=session-existing");

    render(<App />);

    await waitFor(() => expect(clientMock.getSessionSnapshot).toHaveBeenCalledWith("session-existing"));
    expect(clientMock.createSession).not.toHaveBeenCalled();
    expect(await screen.findByText("Session session-existing")).toBeInTheDocument();
    expect(window.location.search).toBe("?sid=session-existing");
  });

  it("falls back to a new session and warns when sid resume fails", async () => {
    clientMock.createSession.mockResolvedValueOnce({ session_id: "session-2" });
    clientMock.getSessionSnapshot.mockImplementation(async (sessionId: string) => {
      if (sessionId === "session-missing") {
        throw new Error("Request failed with status 404");
      }
      return {
        session_id: sessionId,
        tasks: [],
        execution_sessions: [],
        execution_runs: [],
        execution_modes: [],
        bindings: [],
        summaries: [],
        notification_candidates: [],
        personas: [],
        interaction_requests: [],
        attention_items: [],
        executor_capabilities: [],
        executor_nodes: [],
        communication_persona_prompt: "",
      };
    });
    window.history.replaceState({}, "", "/?sid=session-missing");

    render(<App />);

    expect(await screen.findByTestId("shell-warning")).toBeInTheDocument();
    expect(screen.getByText(/Could not resume the requested session/)).toBeInTheDocument();
    expect(screen.getByText(/session-missing/)).toBeInTheDocument();
    expect(screen.getByText("Session session-2")).toBeInTheDocument();
    expect(clientMock.createSession).toHaveBeenCalledTimes(1);
    expect(clientMock.getSessionSnapshot).toHaveBeenNthCalledWith(1, "session-missing");
    expect(clientMock.getSessionSnapshot).toHaveBeenNthCalledWith(2, "session-2");
    expect(window.location.search).toBe("?sid=session-2");
  });

  it("renders Synapse user and assistant stream events in interaction memory", async () => {
    render(<App />);

    await screen.findByText("Session session-1");
    expect(screen.queryByTestId("voice-session-start")).not.toBeInTheDocument();
    expect(screen.getByText("Transcript will appear here.")).toBeInTheDocument();

    await act(async () => {
      socketHarness.emitMessage({
        type: "user_message_appended",
        message_id: "msg-user-1",
        role: "user",
        text: "Please create a follow-up task.",
        source: "user",
      });
    });

    expect(await screen.findByText("Please create a follow-up task.")).toBeInTheDocument();
    expect(screen.getAllByText("Please create a follow-up task.")).toHaveLength(1);
    expect(screen.getByText("Me")).toBeInTheDocument();

    await act(async () => {
      socketHarness.emitMessage({
        type: "assistant_response_completed",
        request_id: "req-1",
        message_id: "msg-assistant-1",
        reply_text: "Hello. How can I help you today?",
        conversational_act: "model_reply",
        affected_task_ids: [],
      });
    });

    expect(await screen.findByText("Hello. How can I help you today?")).toBeInTheDocument();
    expect(screen.getByText("NewBro")).toBeInTheDocument();
    expect(screen.queryByText("Transcript will appear here.")).not.toBeInTheDocument();
    expect(screen.getByText("2 turns")).toBeInTheDocument();
    expect(screen.getByText("Session session-1")).toBeInTheDocument();
  });

  it("switches to runtime persona cards when persona data exists", async () => {
    clientMock.getSessionSnapshot.mockResolvedValueOnce({
      session_id: "session-1",
      tasks: [],
      execution_sessions: [],
      execution_runs: [],
      execution_modes: [],
      bindings: [],
      summaries: [],
      notification_candidates: [],
      personas: [
        {
          persona_id: "persona-1",
          name: "Rook",
          avatar: "/avatars/avatar-01.png",
          base_prompt: "",
          executor_node_id: "node-1",
          status: "busy",
          current_task_id: "task-1234",
        },
        {
          persona_id: "persona-2",
          name: "Vale",
          avatar: "/avatars/avatar-02.png",
          base_prompt: "",
          executor_node_id: "node-2",
          status: "idle",
          current_task_id: null,
        },
      ],
      interaction_requests: [],
      attention_items: [],
      executor_capabilities: [],
      executor_nodes: [
        {
          node_id: "node-1",
          name: "Studio Mac",
          enabled_executors: ["codex"],
          connected_executors: ["codex"],
          connection_status: "connected",
          token_hint: "tok...1111",
          last_connected_at: null,
          last_seen_at: null,
        },
        {
          node_id: "node-2",
          name: "Travel Laptop",
          enabled_executors: ["codex"],
          connected_executors: ["codex"],
          connection_status: "connected",
          token_hint: "tok...2222",
          last_connected_at: null,
          last_seen_at: null,
        },
      ],
      communication_persona_prompt: "",
    });

    render(<App />);

    expect(await screen.findByText("Rook")).toBeInTheDocument();
    expect(screen.getByText("Vale")).toBeInTheDocument();
    expect(screen.getByText("2 live")).toBeInTheDocument();
    expect(screen.queryByText("Atlas")).not.toBeInTheDocument();
  });


  it("does not apply legacy press effects to Home Bro cards", async () => {
    render(<RouterProvider router={getRouter()} />);

    const forgeCard = await screen.findByTestId("bro-card-forge");
    fireEvent.pointerDown(forgeCard);
    fireEvent.pointerUp(forgeCard);

    const card = within(screen.getByTestId("bro-card-forge"));
    expect(screen.getByTestId("bro-card-forge")).not.toHaveAttribute("aria-pressed");
    expect(card.queryByText("preview")).not.toBeInTheDocument();
    expect(card.queryByText("mic on")).not.toBeInTheDocument();
    expect(card.queryByTestId("talking-bars")).not.toBeInTheDocument();
    expect(card.getByText("busy")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("loads the Bros page directly from the URL", async () => {
    window.history.replaceState({}, "", "/bros?sid=session-1");
    const router = getRouter();

    render(<RouterProvider router={router} />);
    await act(async () => {
      await router.load();
    });

    expect(await screen.findByText("Worker Bros")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/bros");
    expect(window.location.search).toBe("?sid=session-1");
    expect(clientMock.createSession).not.toHaveBeenCalled();
    expect(clientMock.getSessionSnapshot).toHaveBeenCalledWith("session-1");
  });

  it("loads the Nodes page directly from the URL", async () => {
    window.history.replaceState({}, "", "/nodes");
    const router = getRouter();

    render(<RouterProvider router={router} />);
    await act(async () => {
      await router.load();
    });

    expect(await screen.findByText("Executor Nodes")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/nodes");
  });

  it("shows a shell-level API error instead of blank data when bootstrap fails", async () => {
    clientMock.createSession.mockRejectedValueOnce(new Error("Request failed with status 404"));

    const router = getRouter();
    render(<RouterProvider router={router} />);
    await act(async () => {
      await router.load();
    });

    expect(await screen.findByText("Unable to reach the Synapse API")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This deployment must proxy /api/* requests to the backend before the shell can load live data.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Atlas")).not.toBeInTheDocument();
  });

  it("keeps shell snapshot bros visible when the Bros page refresh fails", async () => {
    clientMock.getSessionSnapshot.mockResolvedValueOnce({
      session_id: "session-1",
      tasks: [],
      execution_sessions: [],
      execution_runs: [],
      execution_modes: [],
      bindings: [],
      summaries: [],
      notification_candidates: [],
      personas: [
        {
          persona_id: "persona-1",
          name: "Rook",
          avatar: "fox",
          base_prompt: "Stay direct.",
          executor_node_id: "node-1",
          status: "busy",
          current_task_id: "task-1",
        },
      ],
      interaction_requests: [],
      attention_items: [],
      executor_capabilities: [],
      executor_nodes: [
        {
          node_id: "node-1",
          name: "Studio Mac",
          enabled_executors: ["codex"],
          connected_executors: ["codex"],
          connection_status: "connected",
          token_hint: "tok...1111",
          last_connected_at: null,
          last_seen_at: null,
        },
      ],
      communication_persona_prompt: "",
    });
    clientMock.listPersonas.mockRejectedValueOnce(new Error("Bros refresh failed."));
    clientMock.listExecutorNodes.mockRejectedValueOnce(new Error("Nodes refresh failed."));

    window.history.replaceState({}, "", "/bros");
    const router = getRouter();
    render(<RouterProvider router={router} />);
    await act(async () => {
      await router.load();
    });

    expect(await screen.findByText("Worker Bros")).toBeInTheDocument();
    expect(screen.getByText("Rook")).toBeInTheDocument();
    expect(
      screen.getByText("Bros refresh failed. Showing the latest shell snapshot instead."),
    ).toBeInTheDocument();
  });

  it("keeps shell snapshot nodes visible when the Nodes page refresh fails", async () => {
    clientMock.getSessionSnapshot.mockResolvedValueOnce({
      session_id: "session-1",
      tasks: [],
      execution_sessions: [],
      execution_runs: [],
      execution_modes: [],
      bindings: [],
      summaries: [],
      notification_candidates: [],
      personas: [
        {
          persona_id: "persona-1",
          name: "Rook",
          avatar: "fox",
          base_prompt: "Stay direct.",
          executor_node_id: "node-1",
          status: "busy",
          current_task_id: "task-1",
        },
      ],
      interaction_requests: [],
      attention_items: [],
      executor_capabilities: [],
      executor_nodes: [
        {
          node_id: "node-1",
          name: "Studio Mac",
          enabled_executors: ["codex"],
          connected_executors: ["codex"],
          connection_status: "connected",
          token_hint: "tok...1111",
          last_connected_at: null,
          last_seen_at: null,
        },
      ],
      communication_persona_prompt: "",
    });
    clientMock.listExecutorNodes.mockRejectedValueOnce(new Error("Node refresh failed."));
    clientMock.listPersonas.mockRejectedValueOnce(new Error("Persona refresh failed."));

    window.history.replaceState({}, "", "/nodes");
    const router = getRouter();
    render(<RouterProvider router={router} />);
    await act(async () => {
      await router.load();
    });

    expect(await screen.findByText("Executor Nodes")).toBeInTheDocument();
    expect(screen.getByText("Studio Mac")).toBeInTheDocument();
    expect(
      screen.getByText("Node refresh failed. Showing the latest shell snapshot instead."),
    ).toBeInTheDocument();
  });

  it("navigates between left-menu pages and preserves browser history", async () => {
    window.history.replaceState({}, "", "/?sid=session-1");
    const router = getRouter();
    render(<RouterProvider router={router} />);
    await act(async () => {
      await router.load();
    });

    expect(await screen.findByText("Available Bros")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Bros" }));
    await waitFor(() => expect(window.location.pathname).toBe("/bros"));
    expect(window.location.search).toBe("?sid=session-1");
    expect(await screen.findByText("Worker Bros")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Nodes" }));
    await waitFor(() => expect(window.location.pathname).toBe("/nodes"));
    expect(window.location.search).toBe("?sid=session-1");
    expect(await screen.findByText("Executor Nodes")).toBeInTheDocument();

    await act(async () => {
      window.history.back();
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    await waitFor(() => expect(window.location.pathname).toBe("/bros"));
    expect(window.location.search).toBe("?sid=session-1");
    expect(await screen.findByText("Worker Bros")).toBeInTheDocument();
  });
});

describe("buildBroCardModels", () => {
  it("falls back to the seeded sample bros when no personas are available", () => {
    const bros = buildBroCardModels([]);

    expect(bros.map((bro) => bro.name)).toEqual(["Atlas", "Scout", "Muse", "Forge"]);
    expect(bros.every((bro) => bro.source === "sample")).toBe(true);
  });

  it("maps runtime personas into bro cards with busy and idle states", () => {
    const bros = buildBroCardModels([
      {
        persona_id: "persona-1",
        name: "Rook",
        avatar: "/avatars/avatar-01.png",
        executor_node_id: "node-1",
        status: "busy",
        current_task_id: "task-1234",
      },
      {
        persona_id: "persona-2",
        name: "Vale",
        avatar: "/avatars/avatar-02.png",
        executor_node_id: null,
        status: "idle",
        current_task_id: null,
      },
    ], [
      {
        node_id: "node-1",
        name: "Studio Mac",
        connection_status: "connected",
      },
    ]);

    expect(bros).toHaveLength(2);
    expect(bros[0]).toMatchObject({
      id: "persona-1",
      name: "Rook",
      status: "busy",
      liveState: "live",
      taskTitle: "Handle active runtime work",
      source: "runtime",
    });
    expect(bros[1]).toMatchObject({
      id: "persona-2",
      name: "Vale",
      status: "idle",
      liveState: "unbound",
      progressLabel: "Idle",
      source: "runtime",
    });
  });
});
