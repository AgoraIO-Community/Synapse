import { ArrowLeft, CircleDot, Mic, SendHorizontal, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { prepareSttSession, startSttSession, stopSttSession, type SttSessionStartResponse } from "../../lib/connector-client";
import { submitDraftAsrTurn } from "../../lib/session-client";
import { loadAgoraBrowserStack } from "../../lib/voice-runtime";
import { Button } from "../ui/button";
import { BroPortrait } from "./BroPortrait";
import { BroProgress } from "./BroProgress";
import { extractTranscriptText } from "./stt-transcript";
import type { BroCardModel } from "./types";
import type { TaskSummary } from "../../types";

function liveStateText(bro: BroCardModel) {
  if (bro.liveState === "live") return "Live and ready";
  if (bro.liveState === "offline") return "Bound node offline";
  return "Needs node binding";
}

type SttPhase = "idle" | "starting" | "listening" | "stopping" | "error";

type SttResources = {
  rtcClient: any;
  micTrack: any;
  sttSession: SttSessionStartResponse;
};

export function BroDetailPage({
  bro,
  sessionId,
  summary,
  onBack,
}: {
  bro: BroCardModel;
  sessionId: string | null;
  summary: TaskSummary | null;
  onBack: () => void;
}) {
  const [sttPhase, setSttPhase] = useState<SttPhase>("idle");
  const [sttError, setSttError] = useState<string | null>(null);
  const [interimText, setInterimText] = useState("");
  const [finalTurns, setFinalTurns] = useState<string[]>([]);
  const resourcesRef = useRef<SttResources | null>(null);
  const submittedRef = useRef<Set<string>>(new Set());

  async function stopListening() {
    const resources = resourcesRef.current;
    resourcesRef.current = null;
    setSttPhase((current) => (current === "idle" ? current : "stopping"));
    try {
      resources?.micTrack?.stop?.();
      resources?.micTrack?.close?.();
    } catch {}
    try {
      await resources?.rtcClient?.leave?.();
    } catch {}
    try {
      if (resources?.sttSession.stt_session_id) {
        await stopSttSession(resources.sttSession.stt_session_id);
      }
      setSttPhase("idle");
    } catch (error) {
      setSttError(error instanceof Error ? error.message : "Failed to stop STT session.");
      setSttPhase("error");
    }
  }

  async function handleTranscript(payload: unknown) {
    const parsed = extractTranscriptText(payload);
    if (!parsed) return;
    if (!parsed.final) {
      setInterimText(parsed.text);
      return;
    }
    setInterimText("");
    const key = parsed.text.toLowerCase();
    if (submittedRef.current.has(key)) return;
    submittedRef.current.add(key);
    setFinalTurns((current) => [parsed.text, ...current].slice(0, 12));
    if (sessionId) {
      await submitDraftAsrTurn(sessionId, {
        raw_text: parsed.text,
        assigned_bro_id: bro.id,
      });
    }
  }

  async function startListening() {
    if (!sessionId || sttPhase === "starting" || sttPhase === "listening") return;
    setSttPhase("starting");
    setSttError(null);
    let rtcClient: any | null = null;
    let micTrack: any | null = null;
    try {
      const prepared = await prepareSttSession({ synapse_session_id: sessionId, channel_name: sessionId });
      const { AgoraRTC } = await loadAgoraBrowserStack();
      rtcClient = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
      rtcClient.on?.("stream-message", (_uid: string | number, payload: unknown) => {
        void handleTranscript(payload);
      });
      rtcClient.on?.("stream-message-error", (_uid: string | number, error: unknown) => {
        setSttError(error instanceof Error ? error.message : "Failed to receive STT transcript.");
      });
      await rtcClient.join(prepared.app_id, prepared.channel_name, prepared.token, prepared.uid);
      micTrack = await AgoraRTC.createMicrophoneAudioTrack();
      await rtcClient.publish([micTrack]);
      const sttSession = await startSttSession({
        synapse_session_id: sessionId,
        assigned_bro_id: bro.id,
        channel_name: prepared.channel_name,
        user_uid: prepared.uid,
      });
      resourcesRef.current = { rtcClient, micTrack, sttSession };
      setSttPhase("listening");
    } catch (error) {
      try {
        micTrack?.stop?.();
        micTrack?.close?.();
      } catch {}
      try {
        await rtcClient?.leave?.();
      } catch {}
      setSttError(error instanceof Error ? error.message : "Failed to start STT session.");
      setSttPhase("error");
      await stopListening();
    }
  }

  useEffect(() => {
    return () => {
      void stopListening();
    };
  }, []);

  const listening = sttPhase === "listening";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 px-4 pb-4 pt-4 md:px-6 md:pb-6 md:pt-5 xl:px-8 xl:pb-8 xl:pt-6">
      <div className="glass-panel rounded-[32px] border border-white/75 px-5 py-5 md:px-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-4">
            <BroPortrait bro={bro} active={bro.status === "busy"} talking={listening} />
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">Bro detail</div>
              <h1 className="serif-flow mt-2 text-[44px] leading-none tracking-[-0.06em] text-foreground">{bro.name}</h1>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
                <span className="rounded-full border border-border/70 bg-white/60 px-3 py-1">{bro.role}</span>
                <span className="rounded-full border border-border/70 bg-white/60 px-3 py-1">{liveStateText(bro)}</span>
                <span className="rounded-full border border-border/70 bg-white/60 px-3 py-1">{bro.nodeName ?? "No node bound"}</span>
              </div>
            </div>
          </div>
          <Button type="button" variant="outline" className="rounded-full" onClick={onBack}>
            <ArrowLeft className="mr-2 size-4" />
            Back home
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <section className="glass-panel min-h-[520px] rounded-[32px] border border-white/75 p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.24em] text-primary">Draft Brain</div>
              <h2 className="serif-flow mt-2 text-[32px] tracking-[-0.05em]">Draft for {bro.name}</h2>
            </div>
            <span className="rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-primary">{sttPhase}</span>
          </div>
          <div className="mt-8 rounded-[28px] border border-dashed border-border/70 bg-white/50 px-5 py-8 text-center">
            <Mic className="mx-auto size-8 text-primary" />
            <div className="serif-flow mt-4 text-[26px] tracking-[-0.04em]">Speak to draft</div>
            <p className="mx-auto mt-3 max-w-[560px] text-[14px] leading-7 text-muted-foreground">Agora STT listens in this Bro's RTC channel. Final transcript turns update Draft Brain.</p>
            <div className="mt-5 flex justify-center gap-3">
              {listening ? (
                <Button type="button" variant="outline" className="rounded-full" onClick={() => void stopListening()}>
                  <Square className="mr-2 size-4" />
                  Stop
                </Button>
              ) : (
                <Button type="button" className="rounded-full" disabled={!sessionId || sttPhase === "starting"} onClick={() => void startListening()}>
                  <Mic className="mr-2 size-4" />
                  {sttPhase === "starting" ? "Starting..." : "Start Talking"}
                </Button>
              )}
            </div>
            {sttError ? <div className="mt-4 text-[13px] text-[#8d5a62]">{sttError}</div> : null}
            {resourcesRef.current?.sttSession ? (
              <div className="mt-4 text-[11px] leading-5 text-muted-foreground">
                STT agent {resourcesRef.current.sttSession.agent_id} · pub {resourcesRef.current.sttSession.pub_bot_uid} · sub {resourcesRef.current.sttSession.sub_bot_uid}
              </div>
            ) : null}
            <div className="mt-5 text-[12px] text-muted-foreground">Session {sessionId ?? "not connected"}</div>
          </div>
          <div className="mt-5 rounded-[24px] border border-white/75 bg-white/58 p-4">
            <div className="text-[12px] uppercase tracking-[0.18em] text-muted-foreground">Live transcript</div>
            <p className="mt-3 min-h-8 text-[15px] leading-7 text-foreground/80">{interimText || "Interim transcript appears here."}</p>
            <div className="mt-4 grid gap-2">
              {finalTurns.map((turn) => <div key={turn} className="rounded-2xl bg-white/70 px-3 py-2 text-[13px] text-foreground/80">{turn}</div>)}
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button type="button" className="rounded-full" disabled>
              <SendHorizontal className="mr-2 size-4" />
              Send to Bro
            </Button>
            <Button type="button" variant="outline" className="rounded-full" disabled>Clear Draft</Button>
          </div>
        </section>

        <aside className="glass-panel min-h-[520px] rounded-[32px] border border-white/75 p-5">
          <div className="text-[11px] uppercase tracking-[0.24em] text-primary">Runner Brain</div>
          <h2 className="serif-flow mt-2 text-[30px] tracking-[-0.05em]">Current task</h2>
          <div className="mt-5 rounded-[24px] border border-white/75 bg-white/58 p-4">
            <div className="flex items-center gap-2 text-[12px] uppercase tracking-[0.18em] text-muted-foreground"><CircleDot className="size-4 text-primary" />{bro.status}</div>
            <div className="mt-3 text-[18px] font-medium text-foreground">{bro.taskTitle}</div>
            <BroProgress bro={bro} talking={false} />
          </div>
          <div className="mt-4 rounded-[24px] border border-white/75 bg-white/58 p-4">
            <div className="text-[12px] uppercase tracking-[0.18em] text-muted-foreground">Latest summary</div>
            <p className="mt-3 text-[14px] leading-7 text-foreground/80">{summary?.conversational_summary ?? summary?.operational_summary ?? bro.idleNote}</p>
          </div>
          <Button type="button" variant="outline" className="mt-5 w-full rounded-full" disabled={bro.status !== "busy"}><Square className="mr-2 size-4" />Stop Task</Button>
        </aside>
      </div>
    </div>
  );
}
