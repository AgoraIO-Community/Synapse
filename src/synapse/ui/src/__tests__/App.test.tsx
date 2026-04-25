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
    sub_bot_uid: 100102,
    agent_id: "agent-1",
    status: "started",
    languages: ["zh-CN", "en-US"],
    subscribe_audio_uids: ["101"],
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
    expect(await screen.findByRole("button", { name: "Hold to Talk" })).toBeInTheDocument();
    expect(screen.queryByText("Ready · mic off")).not.toBeInTheDocument();
  });

  it("publishes the Bro detail mic before muting it", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    expect(await screen.findByRole("button", { name: "Hold to Talk" })).toBeInTheDocument();
    expect(screen.queryByText("Ready · mic off")).not.toBeInTheDocument();
    expect(voiceHarness.rtcClient.publish).toHaveBeenCalledWith([voiceHarness.micTrack]);
    expect(voiceHarness.micTrack.setEnabled).not.toHaveBeenCalledWith(false);
    expect(voiceHarness.micTrack.setMuted).toHaveBeenCalledWith(true);
    expect(
      voiceHarness.rtcClient.publish.mock.invocationCallOrder[0],
    ).toBeLessThan(voiceHarness.micTrack.setMuted.mock.invocationCallOrder[0]);

    const micButton = screen.getByRole("button", { name: "Hold to Talk" });
    fireEvent.pointerDown(micButton, { pointerId: 1 });
    await waitFor(() => expect(voiceHarness.micTrack.setMuted).toHaveBeenCalledWith(false));
    expect(screen.queryByText("Ready · mic off")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Release to finish" })).toBeInTheDocument();
    expect(screen.queryByTestId("talking-bars")).not.toBeInTheDocument();
    fireEvent.blur(micButton);
    expect(voiceHarness.micTrack.setMuted).toHaveBeenLastCalledWith(false);
    fireEvent.pointerUp(micButton, { pointerId: 1 });
    await waitFor(() => expect(voiceHarness.micTrack.setMuted).toHaveBeenLastCalledWith(true));
    expect(screen.queryByText("Ready · mic off")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hold to Talk" })).toBeInTheDocument();
  });

  it("keeps Bro detail RTC debug and unparsed stream messages out of the UI", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];

    await act(async () => {
      transcriptHandler(200101, { nope: true });
    });

    expect(screen.queryByText(/Voice debug:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/unparsed stream-message/)).not.toBeInTheDocument();
  });

  it("does not poll STT status from Bro detail", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });

    expect(connectorMock.querySttSession).not.toHaveBeenCalled();
    expect(screen.queryByText(/Voice debug:/)).not.toBeInTheDocument();
  });

  it("renders final Bro detail transcript and returned draft content", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, {
        text: "Build a calm\nlanding page",
        isFinal: false,
        time: 100,
        textTs: 110,
      });
      transcriptHandler(200101, {
        text: "with soft motion",
        isFinal: false,
        time: 200,
        textTs: 210,
      });
      transcriptHandler(200101, {
        text: "with",
        isFinal: true,
        time: 200,
        textTs: 220,
      });
    });

    expect(await screen.findByText("Build a calm landing page with soft motion")).toBeInTheDocument();
    expect(screen.queryByText("Listening live")).not.toBeInTheDocument();
    expect(screen.queryByText("Completed turns appear here when ASR marks a segment final.")).not.toBeInTheDocument();
    expect(await screen.findByText("Draft landing page")).toBeInTheDocument();
    expect(screen.getByText("Create a refined landing page concept.")).toBeInTheDocument();
    expect(screen.getByText("Design a polished landing page with a calm hero section.")).toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).toHaveBeenCalledWith("session-existing", {
      raw_text: "Build a calm landing page with soft motion",
      assigned_bro_id: "forge",
    });
  });

  it("prints Bro detail transcript debug as segments displayText and words", async () => {
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, {
        text: "hello world",
        isFinal: false,
        uid: 101,
        time: 100,
        textTs: 120,
        words: [
          { text: "hello", startMs: 100, durationMs: 50, isFinal: true, confidence: 0.95 },
          { text: "world", startMs: 150, durationMs: 60, isFinal: false, confidence: 0.9 },
        ],
      });
    });

    const candidateLog = debugSpy.mock.calls.find(
      ([label]) => label === "[BroDetail][STT] received candidate",
    );
    expect(candidateLog?.[1]).toMatchObject({
      displayText: "hello world",
      segments: [
        {
          key: "101:100",
          uid: "101",
          startTime: 100,
          text: "hello world",
          textTs: 120,
          arrivalIndex: 1,
        },
      ],
      words: [
        { text: "hello", startMs: 100, durationMs: 50, isFinal: true, confidence: 0.95 },
        { text: "world", startMs: 150, durationMs: 60, isFinal: false, confidence: 0.9 },
      ],
      protobuf: null,
    });
    expect(candidateLog?.[1]).not.toHaveProperty("candidate");
    expect(candidateLog?.[1]).not.toHaveProperty("raw");
    debugSpy.mockRestore();
  });

  it("keeps only the latest textTs for each timed Chinese Bro detail sentence", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, { text: "好像在一场大", isFinal: false, time: 100, textTs: 110 });
      transcriptHandler(200101, { text: "型音乐演唱会上面", isFinal: false, time: 100, textTs: 120 });
      transcriptHandler(200101, { text: "南", isFinal: false, time: 200, textTs: 210 });
      transcriptHandler(200101, { text: "美人在美国超级", isFinal: false, time: 200, textTs: 220 });
      transcriptHandler(200101, { text: "碗上面", isFinal: false, time: 200, textTs: 230 });
      transcriptHandler(200101, { text: "大 型", isFinal: false, time: 300, textTs: 310 });
      transcriptHandler(200101, { text: "音乐", isFinal: false, time: 300, textTs: 320 });
      transcriptHandler(200101, { text: "音", isFinal: true, time: 300, textTs: 330 });
    });

    expect(await screen.findByText("型音乐演唱会上面碗上面音乐")).toBeInTheDocument();
    expect(screen.queryByText(/好像在一场大/)).not.toBeInTheDocument();
    expect(screen.queryByText(/美人在美国超级/)).not.toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).toHaveBeenLastCalledWith("session-existing", {
      raw_text: "型音乐演唱会上面碗上面音乐",
      assigned_bro_id: "forge",
    });
  });

  it("ignores untimed Bro detail transcript payloads", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });
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

    expect(screen.queryByText("Still listening to this sentence")).not.toBeInTheDocument();
    expect(screen.queryByText("Listening live")).not.toBeInTheDocument();
    expect(screen.queryByText("Completed turns appear here when ASR marks a segment final.")).not.toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).not.toHaveBeenCalled();
  });

  it("keeps only the latest textTs inside one Bro detail sentence and submits once on mic release", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    const micButton = await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, { text: "第二个片段", isFinal: false, time: 100, textTs: 120 });
      transcriptHandler(200101, { text: "第一个片段", isFinal: false, time: 100, textTs: 110 });
    });

    expect(screen.getByText("第二个片段")).toBeInTheDocument();
    expect(screen.queryByText("第一个片段第二个片段")).not.toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).not.toHaveBeenCalled();

    await act(async () => {
      fireEvent.pointerDown(micButton, { pointerId: 1 });
      await Promise.resolve();
      fireEvent.pointerUp(micButton, { pointerId: 1 });
      await Promise.resolve();
    });

    await waitFor(() => expect(clientMock.submitDraftAsrTurn).toHaveBeenCalledTimes(1));
    expect(clientMock.submitDraftAsrTurn).toHaveBeenCalledWith("session-existing", {
      raw_text: "第二个片段",
      assigned_bro_id: "forge",
    });
  });

  it("drops stale Bro detail ASR candidates for the same sentence", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, { uid: 101, text: "OK，第一个问题", isFinal: false, time: 100, textTs: 300, seqnum: 2 });
      transcriptHandler(200101, { uid: 101, text: "OK", isFinal: false, time: 100, textTs: 200, seqnum: 3 });
      transcriptHandler(200101, { uid: 101, text: "OK，旧修订", isFinal: false, time: 100, textTs: 300, seqnum: 1 });
    });

    expect(screen.getByText("OK，第一个问题")).toBeInTheDocument();
    expect(screen.queryByText("OK")).not.toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).not.toHaveBeenCalled();
  });

  it("holds final fragments until the next non-final for the same sentence", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, { uid: 101, text: "ABCDEFG", isFinal: false, time: 100, textTs: 300 });
    });
    expect(screen.getByText("ABCDEFG")).toBeInTheDocument();

    await act(async () => {
      transcriptHandler(200101, { uid: 101, text: "ABC", isFinal: true, time: 100, textTs: 310 });
      await Promise.resolve();
    });
    expect(screen.getByText("ABCDEFG")).toBeInTheDocument();
    expect(clientMock.submitDraftAsrTurn).toHaveBeenLastCalledWith("session-existing", {
      raw_text: "ABCDEFG",
      assigned_bro_id: "forge",
    });

    await act(async () => {
      transcriptHandler(200101, { uid: 101, text: "DEFG", isFinal: false, time: 100, textTs: 320 });
    });

    expect(screen.getByText("ABCDEFG")).toBeInTheDocument();
    expect(screen.queryByText("ABCDEFGDEFG")).not.toBeInTheDocument();
  });

  it("rebuilds Bro detail ASR by sentence start time using latest textTs per sentence", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    const micButton = await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    await act(async () => {
      transcriptHandler(200101, { uid: 101, text: "第二句", isFinal: false, time: 200, textTs: 210 });
      transcriptHandler(200101, { uid: 101, text: "第一句后半", isFinal: false, time: 100, textTs: 120 });
      transcriptHandler(200101, { uid: 101, text: "第一句前半", isFinal: false, time: 100, textTs: 110 });
    });

    const expectedTranscript = "第一句后半第二句";
    expect(await screen.findByText(expectedTranscript)).toBeInTheDocument();

    await act(async () => {
      fireEvent.pointerDown(micButton, { pointerId: 3 });
      await Promise.resolve();
      fireEvent.pointerUp(micButton, { pointerId: 3 });
      await Promise.resolve();
    });

    await waitFor(() => expect(clientMock.submitDraftAsrTurn).toHaveBeenLastCalledWith("session-existing", {
      raw_text: expectedTranscript,
      assigned_bro_id: "forge",
    }));
  });

  it("submits Bro detail ASR once after silence without duplicating mic release", async () => {
    window.history.replaceState({}, "", "/bros/forge?sid=session-existing");

    render(<RouterProvider router={getRouter()} />);

    const micButton = await screen.findByRole("button", { name: "Hold to Talk" });
    const transcriptHandler = voiceHarness.rtcClient.on.mock.calls.find(
      ([eventName]) => eventName === "stream-message",
    )?.[1];
    expect(transcriptHandler).toBeTypeOf("function");

    vi.useFakeTimers();
    try {
      await act(async () => {
        transcriptHandler(200101, { text: "好像在一场大 型音乐", isFinal: false, time: 100, textTs: 110 });
        vi.advanceTimersByTime(1_200);
        await Promise.resolve();
      });

      expect(clientMock.submitDraftAsrTurn).toHaveBeenCalledTimes(1);
      expect(clientMock.submitDraftAsrTurn).toHaveBeenCalledWith("session-existing", {
        raw_text: "好像在一场大 型音乐",
        assigned_bro_id: "forge",
      });

      await act(async () => {
        fireEvent.pointerDown(micButton, { pointerId: 2 });
        await Promise.resolve();
        fireEvent.pointerUp(micButton, { pointerId: 2 });
        await Promise.resolve();
      });
      expect(clientMock.submitDraftAsrTurn).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
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

  it("shows resume fallback in a floating global message that auto-dismisses", async () => {
    vi.useFakeTimers();
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

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByTestId("global-message")).toBeInTheDocument();
    expect(screen.getByTestId("global-message")).toHaveClass("fixed");
    expect(screen.getByText(/Could not resume the requested session/)).toBeInTheDocument();
    expect(screen.getByText(/session-missing/)).toBeInTheDocument();
    expect(screen.getByText("Session session-2")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(5_999);
    });
    expect(screen.getByTestId("global-message")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByTestId("global-message")).not.toBeInTheDocument();
    expect(clientMock.createSession).toHaveBeenCalledTimes(1);
    expect(clientMock.getSessionSnapshot).toHaveBeenNthCalledWith(1, "session-missing");
    expect(clientMock.getSessionSnapshot).toHaveBeenNthCalledWith(2, "session-2");
    expect(window.location.search).toBe("?sid=session-2");
    vi.useRealTimers();
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
