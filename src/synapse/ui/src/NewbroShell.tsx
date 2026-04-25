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
import { createSession, getConversationSnapshot, getSessionSnapshot, openSessionStream, sendSocketMessage } from "./lib/session-client";
import { readSessionIdFromUrl, replaceSessionIdInUrl } from "./lib/session-url";
import { BroDetailPage } from "./components/newbro/BroDetailPage";
import { BrosPage } from "./components/newbro/BrosPage";
import { BrosPanel } from "./components/newbro/BrosPanel";
import { ConversationMemory } from "./components/newbro/ConversationMemory";
import { NodesPage } from "./components/newbro/NodesPage";
import { Sidebar, type PageId } from "./components/newbro/Sidebar";
import { buildBroCardModels } from "./components/newbro/adapters";
import { useVoiceSession } from "./components/newbro/useVoiceSession";
import type { ExecutionRun, ExecutorNodeRecord, Persona, SessionSnapshot, TaskSummary } from "./types";

export type PageNavigator = (page: PageId) => void;
export type BroNavigator = (broId: string) => void;

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
  const [executionRuns, setExecutionRuns] = useState<ExecutionRun[]>([]);
  const [taskSummaries, setTaskSummaries] = useState<TaskSummary[]>([]);
  const [communicationPersonaPrompt, setCommunicationPersonaPrompt] = useState("");
  const [activeShellSessionId, setActiveShellSessionId] = useState<string | null>(null);
  const [hasLoadedShellSnapshot, setHasLoadedShellSnapshot] = useState(false);
  const [shellError, setShellError] = useState<string | null>(null);
  const [shellWarning, setShellWarning] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; text: string; id: string }>>([]);
  const mountedRef = useRef(false);
  const shellLoadSequenceRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);

  function applySnapshot(snapshot: SessionSnapshot) {
    setRuntimePersonas(snapshot.personas);
    setExecutorNodes(snapshot.executor_nodes ?? []);
    setExecutionRuns(snapshot.execution_runs ?? []);
    setTaskSummaries(snapshot.summaries ?? []);
    setCommunicationPersonaPrompt(snapshot.communication_persona_prompt ?? "");
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
    () => buildBroCardModels(runtimePersonas, executorNodes, executionRuns, taskSummaries),
    [executorNodes, executionRuns, runtimePersonas, taskSummaries],
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

  return {
    bros,
    voiceSession,
    activeShellSessionId,
    hasLoadedShellSnapshot,
    runtimePersonas,
    executorNodes,
    taskSummaries,
    shellError,
    shellWarning,
    setShellError,
    clearGlobalMessage,
    communicationPersonaPrompt,
    sendMessage,
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
    <div className="page-wash min-h-screen bg-background text-foreground antialiased">
      <div className="min-h-screen w-full p-3 md:p-5">
        <div className="glass-panel flex h-[calc(100vh-1.5rem)] flex-col overflow-hidden rounded-[36px] border border-white/75 md:h-[calc(100vh-2.5rem)] lg:flex-row">
          <Sidebar activePage={activePage} onNavigate={onNavigate} />
          <main data-testid="newbro-shell" className="relative flex min-w-0 flex-1 flex-col">
            {children}
          </main>
          {globalMessage && onGlobalMessageDismiss ? (
            <GlobalMessageBanner message={globalMessage} onDismiss={onGlobalMessageDismiss} />
          ) : null}
        </div>
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
        <div className="flex min-h-0 flex-1 flex-col gap-5 px-4 pb-4 pt-4 md:px-6 md:pb-6 md:pt-5 xl:px-8 xl:pb-8 xl:pt-6">
          <section className="min-h-0 flex-1 overflow-y-auto">
            <div className="glass-panel h-full rounded-[32px] border border-white/75 px-4 py-5 md:px-5 md:py-6">
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
            summary={activeSummary}
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
