import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
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

vi.mock("../lib/session-client", () => clientMock);

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
  });

  it("renders the atmospheric split shell scaffolding around the conversation and workbench panes", async () => {
    renderApp();

    expect(await screen.findByTestId("workspace-atmosphere")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-left-pane")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-right-pane")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-split-seam")).toBeInTheDocument();
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
