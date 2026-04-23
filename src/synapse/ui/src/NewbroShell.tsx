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

function useNewbroShellState() {
  const [runtimePersonas, setRuntimePersonas] = useState<Persona[]>([]);
  const [executorNodes, setExecutorNodes] = useState<ExecutorNodeRecord[]>([]);
  const [communicationPersonaPrompt, setCommunicationPersonaPrompt] = useState("");
  const [activeShellSessionId, setActiveShellSessionId] = useState<string | null>(null);
  const [activeBroId, setActiveBroId] = useState<string | null>(null);
  const [isTalking, setIsTalking] = useState(false);
  const mountedRef = useRef(false);
  const idleSessionIdRef = useRef<string | null>(null);
  const shellLoadSequenceRef = useRef(0);

  function applySnapshot(snapshot: SessionSnapshot) {
    setRuntimePersonas(snapshot.personas);
    setExecutorNodes(snapshot.executor_nodes ?? []);
    setCommunicationPersonaPrompt(snapshot.communication_persona_prompt ?? "");
  }

  const syncShellSession = useEffectEvent(
    async (sessionId: string, options: { rememberIdle?: boolean } = {}) => {
      const loadSequence = ++shellLoadSequenceRef.current;
      setActiveShellSessionId(sessionId);

      if (options.rememberIdle) {
        idleSessionIdRef.current = sessionId;
      }

      try {
        const snapshot = await getSessionSnapshot(sessionId);
        if (!mountedRef.current || shellLoadSequenceRef.current !== loadSequence) return;
        startTransition(() => applySnapshot(snapshot));
      } catch {
        if (!mountedRef.current || shellLoadSequenceRef.current !== loadSequence) return;
        startTransition(() => {
          setRuntimePersonas([]);
          setCommunicationPersonaPrompt("");
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
      } catch {
        if (!mountedRef.current) return;
        startTransition(() => {
          setRuntimePersonas([]);
          setCommunicationPersonaPrompt("");
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
    </ShellFrame>
  );
}

export function BrosShellPage({ onNavigate }: { onNavigate: PageNavigator }) {
  const shell = useNewbroShell();

  return (
    <ShellFrame activePage="Bros" onNavigate={onNavigate}>
      {shell.activeShellSessionId ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <BrosPage
            sessionId={shell.activeShellSessionId}
            communicationPersonaPrompt={shell.communicationPersonaPrompt}
          />
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-[14px] text-neutral-400">Connecting to session…</div>
        </div>
      )}
    </ShellFrame>
  );
}

export function NodesShellPage({ onNavigate }: { onNavigate: PageNavigator }) {
  const shell = useNewbroShell();

  return (
    <ShellFrame activePage="Nodes" onNavigate={onNavigate}>
      {shell.activeShellSessionId ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <NodesPage sessionId={shell.activeShellSessionId} />
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center">
          <div className="text-[14px] text-neutral-400">Connecting to session…</div>
        </div>
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
