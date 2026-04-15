import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import App from "../App";
import type { SessionStreamEvent, SessionSnapshot } from "../types";

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
  createSession: vi.fn(async () => ({ session_id: "session-test" })),
  getSessionSnapshot: vi.fn(async () => makeSnapshot()),
  getConversationSnapshot: vi.fn(async () => ({
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
});
