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
import { BrosPage } from "./components/newbro/BrosPage";
import { BrosPanel } from "./components/newbro/BrosPanel";
import { ConversationMemory } from "./components/newbro/ConversationMemory";
import { NodesPage } from "./components/newbro/NodesPage";
import { Sidebar, type PageId } from "./components/newbro/Sidebar";
import { TopVoiceBar } from "./components/newbro/TopVoiceBar";
import { buildBroCardModels } from "./components/newbro/adapters";
import { useVoiceSession } from "./components/newbro/useVoiceSession";
import type { ExecutorNodeRecord, Persona, SessionSnapshot } from "./types";

export type PageNavigator = (page: PageId) => void;

const SHELL_API_ERROR_TITLE = "Unable to reach the Synapse API";
const SHELL_API_ERROR_HINT =
  "This deployment must proxy /api/* requests to the backend before the shell can load live data.";

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
      className="mx-8 my-8 rounded-[28px] border border-red-200 bg-red-50 px-6 py-6 xl:mx-10 xl:my-10"
    >
      <div className="text-[12px] uppercase tracking-[0.22em] text-red-500">Connection problem</div>
      <div className="mt-2 text-[28px] font-medium tracking-[-0.04em] text-red-950">
        {SHELL_API_ERROR_TITLE}
      </div>
      <div className="mt-3 max-w-[720px] text-[14px] leading-7 text-red-800">{detail}</div>
      <div className="mt-3 max-w-[720px] text-[13px] leading-6 text-red-700/90">{SHELL_API_ERROR_HINT}</div>
    </div>
  );
}

function ShellLoadingPanel() {
  return (
    <div
      data-testid="shell-connecting"
      className="mx-8 my-8 rounded-[28px] border border-neutral-200 bg-white px-6 py-6 text-[14px] text-neutral-500 xl:mx-10 xl:my-10"
    >
      Connecting to session…
    </div>
  );
}

function useNewbroShellState() {
  const [runtimePersonas, setRuntimePersonas] = useState<Persona[]>([]);
  const [executorNodes, setExecutorNodes] = useState<ExecutorNodeRecord[]>([]);
  const [communicationPersonaPrompt, setCommunicationPersonaPrompt] = useState("");
  const [activeShellSessionId, setActiveShellSessionId] = useState<string | null>(null);
  const [hasLoadedShellSnapshot, setHasLoadedShellSnapshot] = useState(false);
  const [shellError, setShellError] = useState<string | null>(null);
  const [activeBroId, setActiveBroId] = useState<string | null>(null);
  const [isTalking, setIsTalking] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: "user" | "assistant"; text: string; id: string }>>([]);
  const mountedRef = useRef(false);
  const idleSessionIdRef = useRef<string | null>(null);
  const shellLoadSequenceRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);

  function applySnapshot(snapshot: SessionSnapshot) {
    setRuntimePersonas(snapshot.personas);
    setExecutorNodes(snapshot.executor_nodes ?? []);
    setCommunicationPersonaPrompt(snapshot.communication_persona_prompt ?? "");
    setHasLoadedShellSnapshot(true);
    setShellError(null);
  }

  const syncShellSession = useEffectEvent(
    async (sessionId: string, options: { rememberIdle?: boolean } = {}) => {
      const loadSequence = ++shellLoadSequenceRef.current;
      setActiveShellSessionId(sessionId);
      setShellError(null);
      // Reset chat messages for the new session
      setChatMessages([]);

      if (options.rememberIdle) {
        idleSessionIdRef.current = sessionId;
      }

      try {
        const [snapshot, conversation] = await Promise.all([
          getSessionSnapshot(sessionId),
          getConversationSnapshot(sessionId),
        ]);
        if (!mountedRef.current || shellLoadSequenceRef.current !== loadSequence) return;
        startTransition(() => {
          applySnapshot(snapshot);
          // Hydrate chat messages from server conversation history
          const hydrated = (conversation.conversation_history ?? []).map((entry) => ({
            role: entry.role as "user" | "assistant",
            text: entry.text,
            id: entry.message_id,
          }));
          setChatMessages(hydrated);
        });
      } catch (error: unknown) {
        if (!mountedRef.current || shellLoadSequenceRef.current !== loadSequence) return;
        startTransition(() => {
          setShellError(
            describeApiFailure(error, "Session snapshot request failed before the shell could load."),
          );
        });
      }
    },
  );

  const ensureIdleShellSession = useEffectEvent(async () => {
    if (idleSessionIdRef.current) {
      await syncShellSession(idleSessionIdRef.current);
      return idleSessionIdRef.current;
    }
    const session = await createSession();
    idleSessionIdRef.current = session.session_id;
    await syncShellSession(session.session_id, { rememberIdle: true });
    return session.session_id;
  });

  const { state: voiceSession, start, stop, toggleMute } = useVoiceSession({
    onVoiceSessionActivated: async (sessionId) => {
      await syncShellSession(sessionId);
    },
    onVoiceSessionStopped: async () => {
      await ensureIdleShellSession();
    },
  });

  useEffect(() => {
    mountedRef.current = true;
    async function bootstrapShell() {
      try {
        const session = await createSession();
        if (!mountedRef.current) return;
        idleSessionIdRef.current = session.session_id;
        await syncShellSession(session.session_id, { rememberIdle: true });
      } catch (error: unknown) {
        if (!mountedRef.current) return;
        startTransition(() => {
          setActiveShellSessionId(null);
          setHasLoadedShellSnapshot(false);
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
        if (event.type === "assistant_response_completed") {
          const e = event as unknown as { message_id: string; reply_text: string };
          startTransition(() => {
            setChatMessages((prev) => [
              ...prev,
              { role: "assistant" as const, text: e.reply_text, id: e.message_id },
            ]);
          });
          return;
        }
        if (event.type === "conversation_appended") {
          const e = event as unknown as { message_id: string; text: string; source: string };
          startTransition(() => {
            setChatMessages((prev) => {
              // Deduplicate — assistant_response_completed may have already added this
              if (prev.some((m) => m.id === e.message_id)) return prev;
              return [
                ...prev,
                { role: "assistant" as const, text: e.text, id: e.message_id },
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

  const bros = useMemo(
    () => buildBroCardModels(runtimePersonas, executorNodes),
    [executorNodes, runtimePersonas],
  );

  useEffect(() => {
    if (bros.length === 0) {
      setActiveBroId(null);
      return;
    }
    if (!bros.some((bro) => bro.id === activeBroId)) {
      setActiveBroId(bros[0]?.id ?? null);
    }
  }, [activeBroId, bros]);

  const sendMessage = (text: string): boolean => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    const requestId = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    sendSocketMessage(socket, requestId, text);
    setChatMessages((prev) => [...prev, { role: "user" as const, text, id: requestId }]);
    return true;
  };

  return {
    bros,
    voiceSession,
    activeShellSessionId,
    hasLoadedShellSnapshot,
    runtimePersonas,
    executorNodes,
    shellError,
    activeBroId,
    setActiveBroId,
    isTalking,
    setIsTalking,
    communicationPersonaPrompt,
    start,
    stop,
    toggleMute,
    sendMessage,
    chatMessages,
    voiceConnected: voiceSession.phase === "connected",
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
  children,
}: {
  activePage: PageId;
  onNavigate: PageNavigator;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#f3f0ea] text-neutral-950 antialiased">
      <div className="h-screen w-full p-4 md:p-5">
        <div className="flex h-full overflow-hidden rounded-[32px] border border-neutral-200 bg-[#fcfaf5]">
          <Sidebar activePage={activePage} onNavigate={onNavigate} />
          <main data-testid="newbro-shell" className="flex min-w-0 flex-1 flex-col">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}

export function HomeShellPage({ onNavigate }: { onNavigate: PageNavigator }) {
  const shell = useNewbroShell();
  const [composer, setComposer] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll when chat messages change
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [shell.chatMessages.length]);

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = composer.trim();
    if (!text) return;
    setSendError(null);
    const sent = shell.sendMessage(text);
    if (sent) {
      setComposer("");
    } else {
      setSendError("Not connected. Message was not sent.");
    }
  }

  return (
    <ShellFrame activePage="Home" onNavigate={onNavigate}>
      <TopVoiceBar
        bros={shell.bros}
        voicePhase={shell.voiceSession.phase}
        error={shell.voiceSession.error}
        isMicMuted={shell.voiceSession.isMicMuted}
        transcriptCount={shell.voiceSession.transcript.filter((item) => Boolean(item.text?.trim())).length}
        sessionId={shell.activeShellSessionId}
        onStart={() => {
          void shell.start();
        }}
        onStop={() => {
          void shell.stop();
        }}
        onToggleMute={() => {
          void shell.toggleMute();
        }}
      />

      {shell.shellError && shell.hasLoadedShellSnapshot ? (
        <div className="mx-8 mt-8 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-800 xl:mx-10">
          {shell.shellError}
        </div>
      ) : null}

      {shell.hasLoadedShellSnapshot ? (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-8 px-8 py-8 lg:grid-cols-[minmax(220px,0.56fr)_minmax(840px,1.74fr)] xl:px-10 xl:py-10">
          <section className="flex min-h-0 flex-col pt-4">
            {/* Scrollable conversation area */}
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
              <ConversationMemory
                phase={shell.voiceSession.phase}
                transcript={shell.voiceSession.transcript}
                transcriptSession={shell.voiceSession.transcriptSession}
                error={shell.voiceSession.error}
                lastTranscriptUpdateAt={shell.voiceSession.lastTranscriptUpdateAt}
                lastToolkitMessage={shell.voiceSession.lastToolkitMessage}
              />

              {/* Text chat messages */}
              {shell.chatMessages.length > 0 && (
                <div className="mt-4 max-w-[400px] space-y-2">
                  {shell.chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={msg.role === "user" ? "ml-8" : "mr-8"}
                    >
                      <div
                        className={`rounded-[22px] border px-4 py-3 ${
                          msg.role === "user"
                            ? "rounded-tr-md border-neutral-200 bg-white"
                            : "rounded-tl-md border-neutral-200 bg-[#f1ede5]"
                        }`}
                      >
                        <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-neutral-400">
                          {msg.role === "user" ? "Me" : "NewBro"}
                        </div>
                        <div className="whitespace-pre-wrap text-[13px] leading-6 text-neutral-800">
                          {msg.text}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Pinned input */}
            {sendError && (
              <div className="mt-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
                {sendError}
              </div>
            )}
            <form onSubmit={handleSend} className="mt-3 flex shrink-0 gap-2">
              <input
                type="text"
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
                placeholder="Type a message…"
                className="min-w-0 flex-1 rounded-2xl border border-neutral-200 bg-white px-4 py-2.5 text-[14px] text-neutral-900 placeholder-neutral-400 outline-none transition focus:border-neutral-400 focus:ring-1 focus:ring-neutral-300"
              />
              <button
                type="submit"
                disabled={!composer.trim()}
                className="shrink-0 rounded-2xl border border-neutral-900 bg-neutral-950 px-4 py-2.5 text-[13px] font-medium text-white transition hover:bg-neutral-800 disabled:opacity-30"
              >
                Send
              </button>
            </form>
          </section>

          <section className="flex min-h-0 items-start justify-stretch overflow-y-auto lg:pt-4">
            <BrosPanel
              bros={shell.bros}
              activeBroId={shell.activeBroId}
              isTalking={shell.isTalking}
              voiceConnected={shell.voiceConnected}
              onBroPressStart={(broId) => {
                shell.setActiveBroId(broId);
                shell.setIsTalking(true);
              }}
              onBroPressEnd={() => shell.setIsTalking(false)}
            />
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

export function BrosShellPage({ onNavigate }: { onNavigate: PageNavigator }) {
  const shell = useNewbroShell();

  return (
    <ShellFrame activePage="Bros" onNavigate={onNavigate}>
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
    <ShellFrame activePage="Nodes" onNavigate={onNavigate}>
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
  return (
    <ShellFrame activePage="Settings" onNavigate={onNavigate}>
      <div className="flex flex-1 items-center justify-center">
        <div className="text-[14px] text-neutral-400">Settings coming soon.</div>
      </div>
    </ShellFrame>
  );
}
