import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  getConversationSnapshot: vi.fn(async (sessionId: string) => ({
    session_id: sessionId,
    conversation_history: [],
  })),
  openSessionStream: vi.fn(() => ({ close: vi.fn() })),
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
  buildExecutorRunCommand: vi.fn(() => "./synapse executor run --base-url 'http://localhost:8000' --node-id 'node-1' --token 'token-1'"),
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
    expect(screen.getByTestId("voice-session-start")).toBeInTheDocument();
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

  it("starts voice mode and renders live transcript turns inside interaction memory", async () => {
    render(<App />);

    await screen.findByText("Session session-1");
    fireEvent.click(await screen.findByTestId("voice-session-start"));

    await waitFor(() =>
      expect(connectorMock.prepareConnectorSession).toHaveBeenCalledWith({
        synapse_session_id: "session-1",
      }),
    );
    await waitFor(() => expect(connectorMock.activateConnectorSession).toHaveBeenCalledTimes(1));
    expect(clientMock.getSessionSnapshot).not.toHaveBeenCalledWith("voice-session-1");
    expect(await screen.findByText("Voice session live")).toBeInTheDocument();

    await act(async () => {
      voiceHarness.voiceEvents.TRANSCRIPT_UPDATED?.([
        { turn_id: "turn-1", uid: "9001", text: "Hello. How can I help you today?", status: "final" },
        { turn_id: "turn-2", uid: "101", text: "Please create a follow-up task.", status: "final" },
      ]);
    });

    expect(await screen.findByText("Hello. How can I help you today?")).toBeInTheDocument();
    expect(screen.getByText("Please create a follow-up task.")).toBeInTheDocument();
    expect(screen.getByText("NewBro")).toBeInTheDocument();
    expect(screen.getByText("Me")).toBeInTheDocument();
    expect(screen.getByText("2 transcript turns")).toBeInTheDocument();
    expect(screen.getByText("Session session-1")).toBeInTheDocument();
  });

  it("keeps the last transcript visible after stop without rebinding the shell session", async () => {
    render(<App />);

    await screen.findByText("Session session-1");
    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(connectorMock.activateConnectorSession).toHaveBeenCalledTimes(1));

    await act(async () => {
      voiceHarness.voiceEvents.TRANSCRIPT_UPDATED?.([
        { turn_id: "turn-1", uid: "9001", text: "Hello. How can I help you today?", status: "final" },
      ]);
    });

    fireEvent.click(screen.getByTestId("voice-session-stop"));

    await waitFor(() => {
      expect(screen.getByTestId("voice-session-start")).toBeInTheDocument();
    });

    expect(screen.getByText("Hello. How can I help you today?")).toBeInTheDocument();
    expect(clientMock.createSession).toHaveBeenCalledTimes(1);
    expect(clientMock.getSessionSnapshot).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Last voice session")).not.toBeInTheDocument();
    expect(screen.queryByText("Voice session stopped. Transcript memory retained.")).not.toBeInTheDocument();
  });

  it("mutes and unmutes the microphone while the voice session is live", async () => {
    render(<App />);

    await screen.findByText("Session session-1");
    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(screen.getByTestId("voice-session-mic-toggle")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("voice-session-mic-toggle"));
    await waitFor(() => expect(voiceHarness.micTrack.setEnabled).toHaveBeenCalledWith(false));
    expect(await screen.findByText("Interaction memory is live. The microphone is currently muted.")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("voice-session-mic-toggle"));
    await waitFor(() => expect(voiceHarness.micTrack.setEnabled).toHaveBeenCalledWith(true));
  });

  it("surfaces startup errors without breaking the shell", async () => {
    connectorMock.getConnectorConfig.mockResolvedValueOnce({
      ready: false,
      service_base_url: "https://connectors.example.com",
      defaults: {},
      missing_requirements: ["connectors.agora-convoai.app_id"],
    } as any);

    render(<App />);
    await screen.findByText("Session session-1");
    fireEvent.click(await screen.findByTestId("voice-session-start"));

    expect((await screen.findAllByText(/connectors\.agora-convoai\.app_id/)).length).toBeGreaterThan(0);
    expect(screen.getByTestId("voice-session-start")).toBeInTheDocument();
  });

  it("signals pagehide stop cleanup while a voice session is active", async () => {
    const { unmount } = render(<App />);

    await screen.findByText("Session session-1");
    fireEvent.click(await screen.findByTestId("voice-session-start"));
    await waitFor(() => expect(connectorMock.activateConnectorSession).toHaveBeenCalledTimes(1));

    unmount();

    expect(connectorMock.stopConnectorSessionBeacon).toHaveBeenCalledWith("binding-1");
    expect(runtimeMock.teardownVoiceSession).toHaveBeenCalled();
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
