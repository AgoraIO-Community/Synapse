import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  createSession,
  getConversationSnapshot,
  getSessionSnapshot,
  openSessionStream,
  sendSocketDraftAsrTurn,
  sendSocketMessage,
} from "./lib/session-client";
import { readSessionIdFromUrl, replaceSessionIdInUrl } from "./lib/session-url";
import { BroDetailPage } from "./components/newbro/BroDetailPage";
import { BrosPage } from "./components/newbro/BrosPage";
import { BrosPanel } from "./components/newbro/BrosPanel";
import { ConversationMemory } from "./components/newbro/ConversationMemory";
import { NodesPage } from "./components/newbro/NodesPage";
import { Sidebar, type PageId } from "./components/newbro/Sidebar";
import { buildBroCardModels, buildBroTaskRecords } from "./components/newbro/adapters";
import { useVoiceSession } from "./components/newbro/useVoiceSession";
import { StatusPill, WindowDots } from "./components/newbro/visual";
import type {
  DraftOutputCompletedStreamEvent,
  DraftOutputDeltaStreamEvent,
  DraftOutputFailedStreamEvent,
  DraftOutputStartedStreamEvent,
  DraftSession,
  ExecutionRun,
  ExecutorNodeRecord,
  Persona,
  SessionSnapshot,
  Task,
  TaskSummary,
} from "./types";

export type PageNavigator = (page: PageId) => void;
export type BroNavigator = (broId: string) => void;

type DraftOutputEvent =
  | DraftOutputStartedStreamEvent
  | DraftOutputDeltaStreamEvent
  | DraftOutputCompletedStreamEvent
  | DraftOutputFailedStreamEvent;

const SHELL_API_ERROR_TITLE = "Unable to reach the Synapse API";
const SHELL_API_ERROR_HINT =
  "This deployment must proxy /api/* requests to the backend before the shell can load live data.";
const RESUME_FALLBACK_WARNING_PREFIX = "Could not resume the requested session.";
const GLOBAL_MESSAGE_AUTO_DISMISS_MS = 6_000;

function describeApiFailure(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) {
    return fallback;
  }

  const message = error.message.trim();
  if (!message) {
    return fallback;
  }
  if (message.length > 240) {
    return fallback;
  }
  if (/<(?:!doctype|html|body)/i.test(message)) {
    return fallback;
  }
  return message;
}

function ShellApiErrorPanel({ detail }: { detail: string }) {
  return (
    <div
      data-testid="shell-api-error"
      className="paper-panel mx-4 my-4 rounded-[30px] border border-white/80 px-6 py-6 shadow-[0_24px_54px_-40px_rgba(15,23,42,0.22)] md:mx-6 md:my-6 xl:mx-8 xl:my-8"
    >
      <div className="text-[11px] uppercase tracking-[0.24em] text-[#8d5a62]">Connection problem</div>
      <div className="serif-flow mt-3 text-[32px] tracking-[-0.05em] text-foreground">
        {SHELL_API_ERROR_TITLE}
      </div>
      <div className="mt-3 max-w-[720px] text-[14px] leading-7 text-foreground/82">{detail}</div>
      <div className="mt-3 max-w-[720px] text-[13px] leading-6 text-muted-foreground">{SHELL_API_ERROR_HINT}</div>
    </div>
  );
}

function ShellLoadingPanel() {
  return (
    <div
      data-testid="shell-connecting"
      className="glass-panel mx-4 my-4 rounded-[30px] border border-white/80 px-6 py-6 text-[14px] text-muted-foreground md:mx-6 md:my-6 xl:mx-8 xl:my-8"
    >
      Connecting to session…
    </div>
  );
}

type GlobalMessage = {
  detail: string;
  tone: "error" | "warning";
};

function GlobalMessageBanner({ message, onDismiss }: { message: GlobalMessage; onDismiss: () => void }) {
  const toneClass = message.tone === "error"
    ? "border-red-200 bg-red-50 text-red-600"
    : "border-amber-200 bg-amber-50 text-amber-700";

  useEffect(() => {
    const timer = window.setTimeout(onDismiss, GLOBAL_MESSAGE_AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [message.detail, message.tone, onDismiss]);

  return (
    <div
      data-testid="global-message"
      className={`fixed right-5 top-5 z-50 max-w-[420px] rounded-2xl border px-4 py-3 pr-10 text-[13px] leading-6 shadow-[0_20px_60px_-32px_rgba(15,23,42,0.45)] backdrop-blur md:right-7 md:top-7 ${toneClass}`}
      role="status"
    >
      <div>{message.detail}</div>
      <button
        type="button"
        aria-label="Dismiss message"
        className="absolute right-3 top-2 text-[18px] leading-none opacity-55 transition hover:opacity-90"
        onClick={onDismiss}
      >
        ×
      </button>
    </div>
  );
}

function buildResumeFallbackWarning(sessionId: string) {
  return `${RESUME_FALLBACK_WARNING_PREFIX} Opened a new session instead of ${sessionId}.`;
}

function globalMessageFor(shell: Pick<NewbroShellState, "shellError" | "shellWarning" | "hasLoadedShellSnapshot">): GlobalMessage | null {
  if (shell.shellError && shell.hasLoadedShellSnapshot) {
    return { detail: shell.shellError, tone: "error" };
  }
  if (shell.shellWarning) {
    return { detail: shell.shellWarning, tone: "warning" };
  }
  return null;
}

function useNewbroShellState() {
  const [runtimePersonas, setRuntimePersonas] = useState<Persona[]>([]);
  const [executorNodes, setExecutorNodes] = useState<ExecutorNodeRecord[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [executionRuns, setExecutionRuns] = useState<ExecutionRun[]>([]);
  const [taskSummaries, setTaskSummaries] = useState<TaskSummary[]>([]);
  const [communicationPersonaPrompt, setCommunicationPersonaPrompt] = useState("");
  const [activeShellSessionId, setActiveShellSessionId] = useState<string | null>(null);
  const [hasLoadedShellSnapshot, setHasLoadedShellSnapshot] = useState(false);
  const [shellError, setShellError] = useState<string | null>(null);
  const [shellWarning, setShellWarning] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; text: string; id: string }>>([]);
  const [draftSession, setDraftSession] = useState<DraftSession | null>(null);
  const [latestDraftOutputEvent, setLatestDraftOutputEvent] = useState<DraftOutputEvent | null>(null);
  const mountedRef = useRef(false);
  const shellLoadSequenceRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);

  function applySnapshot(snapshot: SessionSnapshot) {
    setRuntimePersonas(snapshot.personas);
    setExecutorNodes(snapshot.executor_nodes ?? []);
    setTasks(snapshot.tasks ?? []);
    setExecutionRuns(snapshot.execution_runs ?? []);
    setTaskSummaries(snapshot.summaries ?? []);
    setCommunicationPersonaPrompt(snapshot.communication_persona_prompt ?? "");
    setDraftSession(snapshot.draft_session ?? null);
    setHasLoadedShellSnapshot(true);
    setShellError(null);
  }

  const loadShellSession = useEffectEvent(async (sessionId: string) => {
    const loadSequence = ++shellLoadSequenceRef.current;
    setShellError(null);
    const [snapshot, conversation] = await Promise.all([
      getSessionSnapshot(sessionId),
      getConversationSnapshot(sessionId),
    ]);
    if (!mountedRef.current || shellLoadSequenceRef.current !== loadSequence) {
      return;
    }
    startTransition(() => {
      setActiveShellSessionId(sessionId);
      applySnapshot(snapshot);
      const hydrated = (conversation.conversation_history ?? []).map((entry) => ({
        role: entry.role as "user" | "assistant",
        text: entry.text,
        id: entry.message_id,
      }));
      setChatMessages(hydrated);
    });
  });

  const { state: voiceSession, start, stop, toggleMute } = useVoiceSession();

  useEffect(() => {
    mountedRef.current = true;

    async function bootstrapShell() {
      const requestedSessionId = readSessionIdFromUrl();
      if (requestedSessionId) {
        try {
          await loadShellSession(requestedSessionId);
          if (!mountedRef.current) {
            return;
          }
          startTransition(() => setShellWarning(null));
          return;
        } catch {
          try {
            const session = await createSession();
            if (!mountedRef.current) {
              return;
            }
            await loadShellSession(session.session_id);
            if (!mountedRef.current) {
              return;
            }
            startTransition(() => {
              setShellWarning(buildResumeFallbackWarning(requestedSessionId));
            });
            return;
          } catch (error: unknown) {
            if (!mountedRef.current) {
              return;
            }
            startTransition(() => {
              setActiveShellSessionId(null);
              setHasLoadedShellSnapshot(false);
              setShellWarning(null);
              setShellError(
                describeApiFailure(error, "Session bootstrap failed before the shell could start."),
              );
            });
            return;
          }
        }
      }

      try {
        const session = await createSession();
        if (!mountedRef.current) {
          return;
        }
        await loadShellSession(session.session_id);
        if (!mountedRef.current) {
          return;
        }
        startTransition(() => setShellWarning(null));
      } catch (error: unknown) {
        if (!mountedRef.current) {
          return;
        }
        startTransition(() => {
          setActiveShellSessionId(null);
          setHasLoadedShellSnapshot(false);
          setShellWarning(null);
          setShellError(
            describeApiFailure(error, "Session bootstrap failed before the shell could start."),
          );
        });
      }
    }
    void bootstrapShell();
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!activeShellSessionId) {
      socketRef.current = null;
      return undefined;
    }
    const socket = openSessionStream(activeShellSessionId, {
      onOpen: () => {},
      onClose: () => { socketRef.current = null; },
      onError: () => { socketRef.current = null; },
      onMessage: (event) => {
        if (!mountedRef.current) return;
        if (event.type === "snapshot") {
          startTransition(() => applySnapshot(event.snapshot));
          return;
        }
        if (
          event.type === "draft_output_started"
          || event.type === "draft_output_delta"
          || event.type === "draft_output_completed"
          || event.type === "draft_output_failed"
        ) {
          startTransition(() => setLatestDraftOutputEvent(event));
          return;
        }
        if (event.type === "user_message_appended") {
          startTransition(() => {
            setChatMessages((prev) => {
              if (prev.some((m) => m.id === event.message_id)) return prev;
              return [
                ...prev,
                { role: "user" as const, text: event.text, id: event.message_id },
              ];
            });
          });
          return;
        }
        if (event.type === "assistant_response_completed") {
          startTransition(() => {
            setChatMessages((prev) => {
              if (prev.some((m) => m.id === event.message_id)) return prev;
              return [
                ...prev,
                { role: "assistant" as const, text: event.reply_text, id: event.message_id },
              ];
            });
          });
          return;
        }
        if (event.type === "conversation_appended") {
          startTransition(() => {
            setChatMessages((prev) => {
              // Deduplicate — assistant_response_completed may have already added this
              if (prev.some((m) => m.id === event.message_id)) return prev;
              return [
                ...prev,
                { role: "assistant" as const, text: event.text, id: event.message_id },
              ];
            });
          });
        }
      },
    });
    socketRef.current = socket;
    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [activeShellSessionId]);

  useEffect(() => {
    if (!activeShellSessionId) {
      return;
    }
    replaceSessionIdInUrl(activeShellSessionId);
  }, [activeShellSessionId]);

  const bros = useMemo(
    () => buildBroCardModels(runtimePersonas, executorNodes, executionRuns, taskSummaries, tasks),
    [executorNodes, executionRuns, runtimePersonas, taskSummaries, tasks],
  );

  const clearGlobalMessage = useEffectEvent(() => {
    setShellError(null);
    setShellWarning(null);
  });

  const sendMessage = (text: string): boolean => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    const requestId = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    sendSocketMessage(socket, requestId, text);
    return true;
  };

  const submitDraftAsrTurn = (payload: {
    raw_text: string;
    normalized_text?: string;
    confidence?: number;
    assigned_bro_id?: string;
  }): string | null => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return null;
    const requestId = `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    sendSocketDraftAsrTurn(socket, requestId, payload);
    return requestId;
  };

  return {
    bros,
    voiceSession,
    activeShellSessionId,
    hasLoadedShellSnapshot,
    runtimePersonas,
    executorNodes,
    tasks,
    executionRuns,
    taskSummaries,
    shellError,
    shellWarning,
    setShellError,
    clearGlobalMessage,
    communicationPersonaPrompt,
    sendMessage,
    submitDraftAsrTurn,
    draftSession,
    latestDraftOutputEvent,
    chatMessages,
  };
}

type NewbroShellState = ReturnType<typeof useNewbroShellState>;

const NewbroShellContext = createContext<NewbroShellState | null>(null);

export function NewbroShellProvider({ children }: { children: ReactNode }) {
  const value = useNewbroShellState();
  return (
    <NewbroShellContext.Provider value={value}>
      {children}
    </NewbroShellContext.Provider>
  );
}

function useNewbroShell() {
  const value = useContext(NewbroShellContext);
  if (value === null) {
    throw new Error("Newbro shell state is unavailable outside NewbroShellProvider.");
  }
  return value;
}

function ShellFrame({
  activePage,
  onNavigate,
  globalMessage,
  onGlobalMessageDismiss,
  children,
}: {
  activePage: PageId;
  onNavigate: PageNavigator;
  globalMessage?: GlobalMessage | null;
  onGlobalMessageDismiss?: () => void;
  children: ReactNode;
}) {
  return (
    <div className="page-wash min-h-screen bg-[#f7f6f1] text-black antialiased">
      <WindowDots />
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[236px_minmax(0,1fr)]">
        <Sidebar activePage={activePage} onNavigate={onNavigate} />
        <main data-testid="newbro-shell" className="relative flex min-w-0 flex-col overflow-hidden">
          {children}
        </main>
        {globalMessage && onGlobalMessageDismiss ? (
          <GlobalMessageBanner message={globalMessage} onDismiss={onGlobalMessageDismiss} />
        ) : null}
      </div>
    </div>
  );
}

export function HomeShellPage({
  onNavigate,
  onBroNavigate,
}: {
  onNavigate: PageNavigator;
  onBroNavigate?: BroNavigator;
}) {
  const shell = useNewbroShell();

  return (
    <ShellFrame
      activePage="Home"
      onNavigate={onNavigate}
      globalMessage={globalMessageFor(shell)}
      onGlobalMessageDismiss={shell.clearGlobalMessage}
    >

      {shell.hasLoadedShellSnapshot ? (
        <div className="flex min-h-0 flex-1 flex-col px-6 pb-8 pt-8 lg:min-h-screen lg:px-14 lg:pb-10 lg:pt-14 xl:px-20">
          <section className="min-h-0 flex-1 overflow-y-auto subtle-scrollbar">
            <div className="mb-8 flex flex-wrap items-end justify-between gap-6">
              <div>
                <h1 className="newbro-condensed text-[64px] leading-[0.78] sm:text-[96px] xl:text-[118px]">
                  COMMAND CENTER
                  <span className="text-[#ff4b16]">*</span>
                </h1>
                <p className="newbro-mono mt-4 text-xs font-semibold uppercase tracking-[0.22em] text-black/55 sm:text-sm">
                  Available Bros / Runner state / Shared session
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <StatusPill>{shell.bros.filter((bro) => bro.liveState === "live").length} live</StatusPill>
                {shell.activeShellSessionId ? <StatusPill>Session {shell.activeShellSessionId}</StatusPill> : null}
              </div>
            </div>
            <div>
              <div className="sr-only">
                <ConversationMemory
                  phase={shell.voiceSession.phase}
                  messages={shell.chatMessages.map((msg) => ({
                    role: msg.role,
                    text: msg.text,
                    message_id: msg.id,
                  }))}
                  error={shell.voiceSession.error}
                  lastToolkitMessage={shell.voiceSession.lastToolkitMessage}
                />
              </div>
              <BrosPanel
                bros={shell.bros}
                sessionId={shell.activeShellSessionId}
                onBroClick={(broId) => {
                  onBroNavigate?.(broId);
                }}
              />
            </div>
          </section>
        </div>
      ) : shell.shellError ? (
        <ShellApiErrorPanel detail={shell.shellError} />
      ) : (
        <ShellLoadingPanel />
      )}
    </ShellFrame>
  );
}


export function BroDetailShellPage({
  broId,
  onNavigate,
}: {
  broId: string;
  onNavigate: PageNavigator;
}) {
  const shell = useNewbroShell();
  const bro = shell.bros.find((candidate) => candidate.id === broId) ?? null;
  const activeSummary = bro?.source === "runtime"
    ? shell.taskSummaries.find((summary) => summary.task_id === shell.runtimePersonas.find((persona) => persona.persona_id === bro.id)?.current_task_id) ?? null
    : null;
  const activePersona = bro?.source === "runtime"
    ? shell.runtimePersonas.find((persona) => persona.persona_id === bro.id) ?? null
    : null;
  const taskRecords = bro?.source === "runtime"
    ? buildBroTaskRecords(bro.id, {
        activeTaskId: activePersona?.current_task_id ?? null,
        broDetailSessionId: activePersona?.bro_detail_session_id ?? null,
        tasks: shell.tasks,
        executionRuns: shell.executionRuns,
        summaries: shell.taskSummaries,
      })
    : [];

  return (
    <ShellFrame
      activePage="Home"
      onNavigate={onNavigate}
      globalMessage={globalMessageFor(shell)}
      onGlobalMessageDismiss={shell.clearGlobalMessage}
    >
      {shell.hasLoadedShellSnapshot ? (
        bro ? (
          <BroDetailPage
            bro={bro}
            sessionId={shell.activeShellSessionId}
            activeTaskId={activePersona?.current_task_id ?? null}
            summary={activeSummary}
            taskRecords={taskRecords}
            snapshotDraftSession={shell.draftSession}
            latestDraftOutputEvent={shell.latestDraftOutputEvent}
            onSubmitDraftAsrTurn={shell.submitDraftAsrTurn}
            onBack={() => onNavigate("Home")}
            onGlobalError={shell.setShellError}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center p-6">
            <div className="glass-panel max-w-[520px] rounded-[30px] border border-white/75 px-6 py-6 text-center">
              <div className="serif-flow text-[32px] tracking-[-0.05em]">Bro not found</div>
              <p className="mt-3 text-[14px] leading-7 text-muted-foreground">
                This Bro is not available in the current session.
              </p>
              <button
                type="button"
                className="mt-5 rounded-full border border-border/70 bg-white/70 px-4 py-2 text-[14px]"
                onClick={() => onNavigate("Home")}
              >
                Back home
              </button>
            </div>
          </div>
        )
      ) : shell.shellError ? (
        <ShellApiErrorPanel detail={shell.shellError} />
      ) : (
        <ShellLoadingPanel />
      )}
    </ShellFrame>
  );
}

export function BrosShellPage({ onNavigate }: { onNavigate: PageNavigator }) {
  const shell = useNewbroShell();

  return (
    <ShellFrame
      activePage="Bros"
      onNavigate={onNavigate}
      globalMessage={globalMessageFor(shell)}
      onGlobalMessageDismiss={shell.clearGlobalMessage}
    >
      {shell.activeShellSessionId && shell.hasLoadedShellSnapshot ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <BrosPage
            sessionId={shell.activeShellSessionId}
            communicationPersonaPrompt={shell.communicationPersonaPrompt}
            initialPersonas={shell.runtimePersonas}
            initialNodes={shell.executorNodes}
          />
        </div>
      ) : shell.shellError ? (
        <ShellApiErrorPanel detail={shell.shellError} />
      ) : (
        <ShellLoadingPanel />
      )}
    </ShellFrame>
  );
}

export function NodesShellPage({ onNavigate }: { onNavigate: PageNavigator }) {
  const shell = useNewbroShell();

  return (
    <ShellFrame
      activePage="Nodes"
      onNavigate={onNavigate}
      globalMessage={globalMessageFor(shell)}
      onGlobalMessageDismiss={shell.clearGlobalMessage}
    >
      {shell.activeShellSessionId && shell.hasLoadedShellSnapshot ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <NodesPage
            sessionId={shell.activeShellSessionId}
            initialNodes={shell.executorNodes}
            initialPersonas={shell.runtimePersonas}
          />
        </div>
      ) : shell.shellError ? (
        <ShellApiErrorPanel detail={shell.shellError} />
      ) : (
        <ShellLoadingPanel />
      )}
    </ShellFrame>
  );
}

export function SettingsShellPage({ onNavigate }: { onNavigate: PageNavigator }) {
  const shell = useNewbroShell();

  return (
    <ShellFrame
      activePage="Settings"
      onNavigate={onNavigate}
      globalMessage={globalMessageFor(shell)}
      onGlobalMessageDismiss={shell.clearGlobalMessage}
    >
      <div className="flex flex-1 items-center justify-center">
        <div className="text-[14px] text-neutral-400">Settings coming soon.</div>
      </div>
    </ShellFrame>
  );
}
