import { ArrowLeft, CircleDot, Mic, SendHorizontal, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import {
  heartbeatSttSession,
  leaveSttSession,
  prepareSttSession,
  startSttSession,
  type SttSessionPrepareResponse,
  type SttSessionStartResponse,
} from "../../lib/connector-client";
import { submitDraftAsrTurn } from "../../lib/session-client";
import { loadAgoraBrowserStack } from "../../lib/voice-runtime";
import { Button } from "../ui/button";
import { BroPortrait } from "./BroPortrait";
import { BroProgress } from "./BroProgress";
import { extractTranscriptText } from "./stt-transcript";
import type { BroCardModel } from "./types";
import type { TaskSummary } from "../../types";

const HEARTBEAT_INTERVAL_MS = 15_000;
const MAX_VOICE_DEBUG_EVENTS = 5;

type Draft = {
  title: string;
  goal: string;
  constraints?: string[];
  acceptance_criteria?: string[];
  canonical_instruction: string;
  assumptions?: string[];
  missing_info?: string[];
  last_update_summary?: string;
};

type DraftSession = {
  id: string;
  current_draft: Draft | null;
  status: string;
};

function liveStateText(bro: BroCardModel) {
  if (bro.liveState === "live") return "Live and ready";
  if (bro.liveState === "offline") return "Bound node offline";
  return "Needs node binding";
}

type SttPhase =
  | "idle"
  | "preparing_rtc"
  | "joining_rtc"
  | "asr_bot_starting"
  | "ready_mic_off"
  | "capturing"
  | "transcribing"
  | "draft_updating"
  | "error";

type SttResources = {
  rtcClient: any;
  micTrack: any;
  preparedSession: SttSessionPrepareResponse;
  sttSession: SttSessionStartResponse | null;
};

function phaseLabel(phase: SttPhase) {
  if (phase === "preparing_rtc" || phase === "joining_rtc") return "Preparing audio";
  if (phase === "asr_bot_starting") return "Starting ASR bot";
  if (phase === "ready_mic_off") return "Ready · mic off";
  if (phase === "capturing") return "Capturing";
  if (phase === "transcribing") return "Transcribing";
  if (phase === "draft_updating") return "Draft updating";
  if (phase === "error") return "Voice error";
  return "Idle";
}

function payloadShape(payload: unknown) {
  if (payload instanceof Uint8Array) return `${payload.byteLength} bytes`;
  if (payload instanceof ArrayBuffer) return `${payload.byteLength} bytes`;
  if (ArrayBuffer.isView(payload)) return `${payload.byteLength} bytes`;
  if (typeof payload === "string") return `string ${payload.length}`;
  if (!payload || typeof payload !== "object") return typeof payload;
  return `object ${Object.keys(payload as Record<string, unknown>).slice(0, 4).join(",") || "empty"}`;
}

function ListBlock({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{title}</div>
      <div className="mt-2 grid gap-2">
        {items.map((item) => (
          <div key={item} className="rounded-2xl bg-white/65 px-3 py-2 text-[13px] leading-6 text-foreground/78">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function DraftPanel({ draftSession }: { draftSession: DraftSession | null }) {
  const draft = draftSession?.current_draft ?? null;
  if (!draft) {
    return (
      <div className="flex min-h-[240px] flex-1 items-center justify-center rounded-[24px] border border-dashed border-border/70 bg-white/45 p-5 text-center text-[14px] leading-7 text-muted-foreground">
        No draft yet. Hold the mic to start shaping one.
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto rounded-[24px] border border-white/75 bg-white/58 p-4">
      <div className="text-[11px] uppercase tracking-[0.18em] text-primary">Current draft</div>
      <h3 className="serif-flow mt-2 text-[28px] tracking-[-0.05em] text-foreground">{draft.title}</h3>
      {draft.last_update_summary ? <p className="mt-2 text-[12px] text-muted-foreground">{draft.last_update_summary}</p> : null}
      <div className="mt-4 rounded-[22px] bg-white/70 p-4">
        <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Goal</div>
        <p className="mt-2 text-[14px] leading-7 text-foreground/82">{draft.goal}</p>
      </div>
      <div className="mt-3 rounded-[22px] bg-white/70 p-4">
        <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Canonical instruction</div>
        <p className="mt-2 whitespace-pre-wrap text-[14px] leading-7 text-foreground/82">{draft.canonical_instruction}</p>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <ListBlock title="Constraints" items={draft.constraints} />
        <ListBlock title="Acceptance" items={draft.acceptance_criteria} />
        <ListBlock title="Missing info" items={draft.missing_info} />
        <ListBlock title="Assumptions" items={draft.assumptions} />
      </div>
    </div>
  );
}

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
  const [latestTranscriptText, setLatestTranscriptText] = useState("");
  const [interimText, setInterimText] = useState("");
  const [finalTurns, setFinalTurns] = useState<string[]>([]);
  const [draftSession, setDraftSession] = useState<DraftSession | null>(null);
  const [voiceDebugEvents, setVoiceDebugEvents] = useState<string[]>([]);
  const resourcesRef = useRef<SttResources | null>(null);
  const submittedRef = useRef<Set<string>>(new Set());
  const activePointerIdRef = useRef<number | null>(null);
  const mountedRef = useRef(false);
  const generationRef = useRef(0);

  const appendVoiceDebugEvent = useCallback((event: string) => {
    setVoiceDebugEvents((current) => [event, ...current].slice(0, MAX_VOICE_DEBUG_EVENTS));
  }, []);

  const leaveResources = useCallback(async (resources: SttResources | null) => {
    if (!resources) return;
    try {
      await resources.micTrack?.setMuted?.(true);
    } catch {}
    try {
      resources.micTrack?.stop?.();
      resources.micTrack?.close?.();
    } catch {}
    try {
      await resources.rtcClient?.leave?.();
    } catch {}
    try {
      if (resources.sttSession?.stt_session_id) {
        await leaveSttSession({ stt_session_id: resources.sttSession.stt_session_id });
      } else if (resources.preparedSession.prepared_stt_session_id) {
        await leaveSttSession({ prepared_stt_session_id: resources.preparedSession.prepared_stt_session_id });
      }
    } catch (error) {
      if (mountedRef.current) {
        setSttError(error instanceof Error ? error.message : "Failed to leave STT session.");
      }
    }
  }, []);

  const handleTranscript = useCallback(async (payload: unknown) => {
    const parsed = extractTranscriptText(payload);
    if (!parsed) {
      appendVoiceDebugEvent(`unparsed stream-message · ${payloadShape(payload)}`);
      return;
    }
    appendVoiceDebugEvent(`stream-message parsed · ${parsed.final ? "final" : "interim"}`);
    setLatestTranscriptText(parsed.text);
    if (!parsed.final) {
      setInterimText(parsed.text);
      return;
    }
    setInterimText("");
    setSttPhase("draft_updating");
    const key = parsed.text.toLowerCase();
    if (submittedRef.current.has(key)) {
      setSttPhase("ready_mic_off");
      return;
    }
    submittedRef.current.add(key);
    setFinalTurns((current) => [parsed.text, ...current].slice(0, 12));
    if (sessionId) {
      try {
        const nextDraftSession = await submitDraftAsrTurn(sessionId, {
          raw_text: parsed.text,
          assigned_bro_id: bro.id,
        });
        setDraftSession(nextDraftSession as DraftSession);
        setSttPhase("ready_mic_off");
      } catch (error) {
        setSttError(error instanceof Error ? error.message : "Failed to update draft from transcript.");
        setSttPhase("error");
      }
    } else {
      setSttPhase("ready_mic_off");
    }
  }, [appendVoiceDebugEvent, bro.id, sessionId]);

  useEffect(() => {
    mountedRef.current = true;
    const generation = ++generationRef.current;
    let rtcClient: any | null = null;
    let micTrack: any | null = null;
    let preparedSession: SttSessionPrepareResponse | null = null;

    async function start() {
      if (!sessionId) return;
      setSttPhase("preparing_rtc");
      setSttError(null);
      try {
        preparedSession = await prepareSttSession({ synapse_session_id: sessionId, assigned_bro_id: bro.id });
        if (!mountedRef.current || generationRef.current !== generation) return;
        setSttPhase("joining_rtc");
        const { AgoraRTC } = await loadAgoraBrowserStack();
        rtcClient = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
        rtcClient.on?.("stream-message", (uid: string | number, payload: unknown) => {
          appendVoiceDebugEvent(`stream-message from ${uid} · ${payloadShape(payload)}`);
          void handleTranscript(payload);
        });
        rtcClient.on?.("stream-message-error", (_uid: string | number, error: unknown) => {
          setSttError(error instanceof Error ? error.message : "Failed to receive STT transcript.");
        });
        rtcClient.on?.("user-joined", (user: any) => appendVoiceDebugEvent(`user joined: ${user?.uid ?? "unknown"}`));
        rtcClient.on?.("user-left", (user: any) => appendVoiceDebugEvent(`user left: ${user?.uid ?? "unknown"}`));
        rtcClient.on?.("user-published", (user: any, mediaType: string) => appendVoiceDebugEvent(`user published: ${user?.uid ?? "unknown"} ${mediaType}`));
        rtcClient.on?.("user-unpublished", (user: any, mediaType: string) => appendVoiceDebugEvent(`user unpublished: ${user?.uid ?? "unknown"} ${mediaType}`));
        rtcClient.on?.("connection-state-change", (current: string, previous: string) => appendVoiceDebugEvent(`rtc ${previous} -> ${current}`));
        await rtcClient.join(preparedSession.app_id, preparedSession.channel_name, preparedSession.token, preparedSession.uid);
        micTrack = await AgoraRTC.createMicrophoneAudioTrack();
        await rtcClient.publish([micTrack]);
        await micTrack.setMuted?.(true);
        resourcesRef.current = { rtcClient, micTrack, preparedSession, sttSession: null };
        if (!mountedRef.current || generationRef.current !== generation) return;
        setSttPhase("asr_bot_starting");
        const sttSession = await startSttSession({
          prepared_stt_session_id: preparedSession.prepared_stt_session_id,
        });
        resourcesRef.current = { rtcClient, micTrack, preparedSession, sttSession };
        appendVoiceDebugEvent(`stt bots pub ${sttSession.pub_bot_uid} · sub ${sttSession.sub_bot_uid}`);
        if (!mountedRef.current || generationRef.current !== generation) return;
        setSttPhase("ready_mic_off");
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to start STT session.";
        if (mountedRef.current && generationRef.current === generation) {
          setSttError(message);
          setSttPhase("error");
        }
        await leaveResources(
          preparedSession
            ? { rtcClient, micTrack, preparedSession, sttSession: resourcesRef.current?.sttSession ?? null }
            : null,
        );
      }
    }

    void start();

    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
      const resources = resourcesRef.current;
      resourcesRef.current = null;
      void leaveResources(resources);
    };
  }, [appendVoiceDebugEvent, bro.id, handleTranscript, leaveResources, sessionId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const sttSessionId = resourcesRef.current?.sttSession?.stt_session_id;
      if (sttSessionId) {
        void heartbeatSttSession(sttSessionId).catch((error) => {
          if (mountedRef.current) {
            setSttError(error instanceof Error ? error.message : "Failed to heartbeat STT session.");
          }
        });
      }
    }, HEARTBEAT_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  async function setMicEnabled(enabled: boolean) {
    const micTrack = resourcesRef.current?.micTrack;
    if (!micTrack || sttPhase === "error") return;
    try {
      await micTrack.setMuted?.(!enabled);
      setSttPhase(enabled ? "capturing" : "transcribing");
    } catch (error) {
      setSttError(error instanceof Error ? error.message : "Failed to toggle microphone.");
      setSttPhase("error");
    }
  }

  function handleMicPointerDown(event: PointerEvent<HTMLButtonElement>) {
    activePointerIdRef.current = event.pointerId;
    event.currentTarget.setPointerCapture(event.pointerId);
    void setMicEnabled(true);
  }

  function handleMicPointerUp(event: PointerEvent<HTMLButtonElement>) {
    activePointerIdRef.current = null;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    void setMicEnabled(false);
  }

  function handleMicKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.repeat || (event.key !== " " && event.key !== "Enter")) return;
    event.preventDefault();
    void setMicEnabled(true);
  }

  function handleMicKeyUp(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    void setMicEnabled(false);
  }

  const readyForMic = sttPhase === "ready_mic_off" || sttPhase === "capturing" || sttPhase === "transcribing" || sttPhase === "draft_updating";
  const capturing = sttPhase === "capturing";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4 pt-3 md:px-6 md:pb-6 xl:px-8 xl:pb-8">
      <div className="glass-panel rounded-[24px] border border-white/75 px-4 py-3 md:px-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <BroPortrait bro={bro} active={bro.status === "busy"} talking={false} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">Bro detail</div>
                <span className="rounded-full border border-primary/15 bg-primary/10 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-primary">{phaseLabel(sttPhase)}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <h1 className="serif-flow text-[30px] leading-none tracking-[-0.055em] text-foreground">{bro.name}</h1>
                <span className="rounded-full border border-border/70 bg-white/60 px-2.5 py-1 text-[11px] text-muted-foreground">{bro.role}</span>
                <span className="rounded-full border border-border/70 bg-white/60 px-2.5 py-1 text-[11px] text-muted-foreground">{liveStateText(bro)}</span>
              </div>
            </div>
          </div>
          <Button type="button" variant="outline" className="h-9 rounded-full px-3" onClick={onBack}>
            <ArrowLeft className="mr-2 size-4" />
            Back home
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-[1.35fr_0.65fr]">
        <section className="glass-panel flex min-h-[520px] flex-col rounded-[28px] border border-white/75 p-4">
          <div className="flex flex-col gap-3 rounded-[22px] border border-white/75 bg-white/55 p-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-primary">Draft Brain</div>
              <div className="mt-1 text-[13px] text-muted-foreground">Hold the mic to shape a draft for {bro.name}.</div>
              {sttError ? <div className="mt-2 text-[13px] text-[#8d5a62]">{sttError}</div> : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-border/70 bg-white/65 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{phaseLabel(sttPhase)}</span>
              <Button
                type="button"
                className="h-10 rounded-full px-4"
                disabled={!sessionId || !readyForMic || sttPhase === "draft_updating"}
                onPointerDown={handleMicPointerDown}
                onPointerUp={handleMicPointerUp}
                onPointerCancel={(event) => handleMicPointerUp(event)}
                onKeyDown={handleMicKeyDown}
                onKeyUp={handleMicKeyUp}
                onBlur={() => {
                  if (activePointerIdRef.current === null) void setMicEnabled(false);
                }}
              >
                <Mic className="mr-2 size-4" />
                {capturing ? "Release to transcribe" : "Hold to Talk"}
              </Button>
            </div>
            {voiceDebugEvents.length > 0 ? (
              <div className="mt-2 text-[11px] leading-5 text-muted-foreground">
                Voice debug: {voiceDebugEvents.slice(0, 3).join(" · ")}
              </div>
            ) : null}
          </div>

          <div className="mt-3 grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[0.85fr_1.15fr]">
            <div className="flex min-h-[260px] flex-col rounded-[24px] border border-white/75 bg-white/58 p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Live transcript</div>
              <p className="mt-3 min-h-10 rounded-2xl bg-white/60 px-3 py-2 text-[14px] leading-7 text-foreground/78">{latestTranscriptText || "Latest transcript will appear here."}</p>
              {interimText ? <div className="mt-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Listening live</div> : null}
              <div className="mt-3 min-h-0 flex-1 overflow-auto pr-1">
                <div className="grid gap-2">
                  {finalTurns.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-border/70 bg-white/45 px-3 py-6 text-center text-[13px] leading-6 text-muted-foreground">Completed turns appear here when ASR marks a segment final.</div>
                  ) : null}
                  {finalTurns.map((turn) => <div key={turn} className="rounded-2xl bg-white/72 px-3 py-2 text-[13px] leading-6 text-foreground/80">{turn}</div>)}
                </div>
              </div>
            </div>

            <div className="flex min-h-[260px] flex-col">
              <DraftPanel draftSession={draftSession} />
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" className="h-9 rounded-full" disabled>
              <SendHorizontal className="mr-2 size-4" />
              Send to Bro
            </Button>
            <Button type="button" variant="outline" className="h-9 rounded-full" disabled>Clear Draft</Button>
          </div>
        </section>

        <aside className="glass-panel min-h-[420px] rounded-[28px] border border-white/75 p-4">
          <div className="text-[11px] uppercase tracking-[0.22em] text-primary">Runner Brain</div>
          <h2 className="serif-flow mt-1 text-[26px] tracking-[-0.05em]">Current task</h2>
          <div className="mt-4 rounded-[22px] border border-white/75 bg-white/58 p-4">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground"><CircleDot className="size-4 text-primary" />{bro.status}</div>
            <div className="mt-3 text-[16px] font-medium text-foreground">{bro.taskTitle}</div>
            <BroProgress bro={bro} talking={false} />
          </div>
          <div className="mt-3 rounded-[22px] border border-white/75 bg-white/58 p-4">
            <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Latest summary</div>
            <p className="mt-3 text-[13px] leading-6 text-foreground/80">{summary?.conversational_summary ?? summary?.operational_summary ?? bro.idleNote}</p>
          </div>
          <Button type="button" variant="outline" className="mt-4 w-full rounded-full" disabled={bro.status !== "busy"}><Square className="mr-2 size-4" />Stop Task</Button>
        </aside>
      </div>
    </div>
  );
}
