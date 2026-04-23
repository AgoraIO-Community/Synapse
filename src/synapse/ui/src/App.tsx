import { startTransition, useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { createSession, getSessionSnapshot } from "./lib/session-client";
import {
  BrosPage,
  BrosPanel,
  ConversationMemory,
  Sidebar,
  TopVoiceBar,
  buildBroCardModels,
  useVoiceSession,
} from "./components/newbro";
import type { PageId } from "./components/newbro";
import type { Persona, SessionSnapshot } from "./types";

export default function App() {
  const [activePage, setActivePage] = useState<PageId>("Home");
  const [runtimePersonas, setRuntimePersonas] = useState<Persona[]>([]);
  const [communicationPersonaPrompt, setCommunicationPersonaPrompt] = useState("");
  const [activeShellSessionId, setActiveShellSessionId] = useState<string | null>(null);
  const [activeBroId, setActiveBroId] = useState<string | null>(null);
  const [isTalking, setIsTalking] = useState(false);
  const mountedRef = useRef(false);
  const idleSessionIdRef = useRef<string | null>(null);
  const shellLoadSequenceRef = useRef(0);

  function applySnapshot(snapshot: SessionSnapshot) {
    setRuntimePersonas(snapshot.personas);
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
    return () => { mountedRef.current = false; };
  }, []);

  const bros = useMemo(() => buildBroCardModels(runtimePersonas), [runtimePersonas]);

  useEffect(() => {
    if (bros.length === 0) { setActiveBroId(null); return; }
    if (!bros.some((bro) => bro.id === activeBroId)) {
      setActiveBroId(bros[0]?.id ?? null);
    }
  }, [activeBroId, bros]);

  const voiceConnected = voiceSession.phase === "connected";

  return (
    <div className="min-h-screen bg-[#f3f0ea] text-neutral-950 antialiased">
      <div className="h-screen w-full p-4 md:p-5">
        <div className="flex h-full overflow-hidden rounded-[32px] border border-neutral-200 bg-[#fcfaf5]">
          <Sidebar activePage={activePage} onNavigate={setActivePage} />

          <main data-testid="newbro-shell" className="flex min-w-0 flex-1 flex-col">
            {activePage === "Home" && (
              <>
                <TopVoiceBar
                  bros={bros}
                  voicePhase={voiceSession.phase}
                  error={voiceSession.error}
                  isMicMuted={voiceSession.isMicMuted}
                  transcriptCount={voiceSession.transcript.filter((item) => Boolean(item.text?.trim())).length}
                  sessionId={activeShellSessionId}
                  onStart={() => { void start(); }}
                  onStop={() => { void stop(); }}
                  onToggleMute={() => { void toggleMute(); }}
                />

                <div className="grid min-h-0 flex-1 grid-cols-1 gap-8 overflow-auto px-8 py-8 lg:grid-cols-[minmax(220px,0.56fr)_minmax(840px,1.74fr)] xl:px-10 xl:py-10">
                  <section className="flex min-h-0 flex-col pt-4">
                    <ConversationMemory
                      phase={voiceSession.phase}
                      transcript={voiceSession.transcript}
                      transcriptSession={voiceSession.transcriptSession}
                      error={voiceSession.error}
                      lastTranscriptUpdateAt={voiceSession.lastTranscriptUpdateAt}
                      lastToolkitMessage={voiceSession.lastToolkitMessage}
                    />
                  </section>

                  <section className="flex items-start justify-stretch lg:pt-4">
                    <BrosPanel
                      bros={bros}
                      activeBroId={activeBroId}
                      isTalking={isTalking}
                      voiceConnected={voiceConnected}
                      onBroPressStart={(broId) => { setActiveBroId(broId); setIsTalking(true); }}
                      onBroPressEnd={() => setIsTalking(false)}
                    />
                  </section>
                </div>
              </>
            )}

            {activePage === "Bros" && activeShellSessionId && (
              <div className="min-h-0 flex-1 overflow-auto">
                <BrosPage
                  sessionId={activeShellSessionId}
                  communicationPersonaPrompt={communicationPersonaPrompt}
                />
              </div>
            )}

            {activePage === "Bros" && !activeShellSessionId && (
              <div className="flex flex-1 items-center justify-center">
                <div className="text-[14px] text-neutral-400">Connecting to session…</div>
              </div>
            )}

            {activePage === "Settings" && (
              <div className="flex flex-1 items-center justify-center">
                <div className="text-[14px] text-neutral-400">Settings coming soon.</div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
