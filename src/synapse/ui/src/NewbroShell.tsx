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
import { createSession, getSessionSnapshot, openSessionStream } from "./lib/session-client";
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
  const mountedRef = useRef(false);
  const idleSessionIdRef = useRef<string | null>(null);
  const shellLoadSequenceRef = useRef(0);

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

      if (options.rememberIdle) {
        idleSessionIdRef.current = sessionId;
      }

      try {
        const snapshot = await getSessionSnapshot(sessionId);
        if (!mountedRef.current || shellLoadSequenceRef.current !== loadSequence) return;
        startTransition(() => applySnapshot(snapshot));
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
      return undefined;
    }
    const socket = openSessionStream(activeShellSessionId, {
      onOpen: () => {},
      onClose: () => {},
      onError: () => {},
      onMessage: (event) => {
        if (event.type !== "snapshot" || !mountedRef.current) {
          return;
        }
        startTransition(() => applySnapshot(event.snapshot));
      },
    });
    return () => {
      socket.close();
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
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-8 overflow-auto px-8 py-8 lg:grid-cols-[minmax(220px,0.56fr)_minmax(840px,1.74fr)] xl:px-10 xl:py-10">
          <section className="flex min-h-0 flex-col pt-4">
            <ConversationMemory
              phase={shell.voiceSession.phase}
              transcript={shell.voiceSession.transcript}
              transcriptSession={shell.voiceSession.transcriptSession}
              error={shell.voiceSession.error}
              lastTranscriptUpdateAt={shell.voiceSession.lastTranscriptUpdateAt}
              lastToolkitMessage={shell.voiceSession.lastToolkitMessage}
            />
          </section>

          <section className="flex items-start justify-stretch lg:pt-4">
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
