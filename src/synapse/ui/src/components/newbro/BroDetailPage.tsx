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
import { describeProtobufTranscriptPayload, describeTranscriptPayload, extractTranscriptText, type ExtractedSttTranscript } from "./stt-transcript";
import type { BroCardModel } from "./types";
import type { TaskSummary } from "../../types";

const HEARTBEAT_INTERVAL_MS = 15_000;
const STT_SILENCE_COMMIT_MS = 1_200;
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

function normalizeTranscriptSegmentForDisplay(text: string) {
  return text.replace(/\s*\n+\s*/g, " ").trim();
}

function hasCjkBoundary(current: string, next: string) {
  return /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]$/u.test(current)
    && /^[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(next);
}

function appendTranscriptSegment(current: string, next: string) {
  const segment = normalizeTranscriptSegmentForDisplay(next);
  if (!segment) return current;
  if (!current) return segment;
  if (
    /[,.;:!?，。！？、；：）】》」』]$/.test(current)
    || /^[,.;:!?，。！？、；：）】》」』]/.test(segment)
    || hasCjkBoundary(current, segment)
  ) {
    return `${current}${segment}`;
  }
  return `${current} ${segment}`;
}

function composeTranscriptText(segments: string[]) {
  return segments.reduce((current, segment) => appendTranscriptSegment(current, segment), "");
}

type SentenceSegment = {
  uid: string;
  startTime: number;
  text: string;
  textTs: number;
  revision: number;
  arrivalIndex: number;
  pendingFinal?: {
    text: string;
    textTs: number;
    revision: number;
    arrivalIndex: number;
  };
};

type SentenceUpdateResult = {
  text: string;
  action: "create-sentence" | "replace-sentence" | "hold-final-fragment" | "replace-sentence-with-held-final" | "drop-missing-time-metadata" | "drop-stale-sentence";
  segments: Map<string, SentenceSegment>;
  sentenceKey?: string;
  sentenceStartTime?: number;
  existingTextTs?: number;
  textTs?: number;
  pendingFinalTextTs?: number;
  pendingFinalLength?: number;
  heldFinalApplied?: boolean;
  sentencesCount: number;
  reason?: string;
};

function transcriptUid(candidate: ExtractedSttTranscript) {
  return candidate.uid == null ? "default" : String(candidate.uid);
}

function sentenceKey(candidate: ExtractedSttTranscript) {
  if (candidate.time == null) return null;
  return `${transcriptUid(candidate)}:${candidate.time}`;
}

function transcriptEndTime(candidate: ExtractedSttTranscript) {
  if (candidate.textTs != null) return candidate.textTs;
  if (candidate.time != null && candidate.durationMs != null) return candidate.time + candidate.durationMs;
  return candidate.time;
}

function transcriptRevision(candidate: ExtractedSttTranscript, arrivalIndex: number) {
  return candidate.seqnum
    ?? candidate.offtime
    ?? candidate.durationMs
    ?? transcriptEndTime(candidate)
    ?? arrivalIndex;
}

function rebuildSentenceTranscript(segments: Map<string, SentenceSegment>) {
  return composeTranscriptText([...segments.values()].sort((left, right) => {
    if (left.startTime !== right.startTime) return left.startTime - right.startTime;
    return left.arrivalIndex - right.arrivalIndex;
  }).map((segment) => segment.text).filter(Boolean));
}

function serializeTranscriptSegmentsForDebug(segments: Map<string, SentenceSegment>) {
  return [...segments.entries()]
    .sort(([, left], [, right]) => {
      if (left.startTime !== right.startTime) return left.startTime - right.startTime;
      return left.arrivalIndex - right.arrivalIndex;
    })
    .map(([key, segment]) => ({
      key,
      uid: segment.uid,
      startTime: segment.startTime,
      text: segment.text,
      textTs: segment.textTs,
      revision: segment.revision,
      arrivalIndex: segment.arrivalIndex,
      ...(segment.pendingFinal ? { pendingFinal: segment.pendingFinal } : {}),
    }));
}

function updateSentenceSegments(
  segments: Map<string, SentenceSegment>,
  candidate: ExtractedSttTranscript,
  arrivalIndex: number,
): SentenceUpdateResult {
  const key = sentenceKey(candidate);
  if (!key || candidate.time == null || candidate.textTs == null) {
    return { text: rebuildSentenceTranscript(segments), action: "drop-missing-time-metadata", segments, sentencesCount: segments.size, reason: "missing time or textTs" };
  }

  const revision = transcriptRevision(candidate, arrivalIndex);
  const nextSegments = new Map(segments);
  const segment = nextSegments.get(key);
  if (candidate.final) {
    const pendingFinal = { text: candidate.text, textTs: candidate.textTs, revision, arrivalIndex };
    nextSegments.set(key, segment
      ? { ...segment, pendingFinal }
      : {
          uid: transcriptUid(candidate),
          startTime: candidate.time,
          text: "",
          textTs: candidate.textTs,
          revision,
          arrivalIndex,
          pendingFinal,
        });
    return {
      text: rebuildSentenceTranscript(segments),
      action: "hold-final-fragment",
      segments: nextSegments,
      sentenceKey: key,
      sentenceStartTime: candidate.time,
      existingTextTs: segment?.textTs,
      textTs: candidate.textTs,
      pendingFinalTextTs: candidate.textTs,
      pendingFinalLength: candidate.text.length,
      sentencesCount: nextSegments.size,
    };
  }

  if (segment) {
    const isOlderTextTs = candidate.textTs < segment.textTs;
    const isSameTextTsStaleRevision = candidate.textTs === segment.textTs && revision < segment.revision;
    if (isOlderTextTs || isSameTextTsStaleRevision) {
      return {
        text: rebuildSentenceTranscript(segments),
        action: "drop-stale-sentence",
        segments,
        sentenceKey: key,
        sentenceStartTime: candidate.time,
        existingTextTs: segment.textTs,
        textTs: candidate.textTs,
        sentencesCount: segments.size,
        reason: isOlderTextTs ? "older textTs" : "stale revision",
      };
    }
  }

  const appliedText = segment?.pendingFinal ? `${segment.pendingFinal.text}${candidate.text}` : candidate.text;

  nextSegments.set(key, {
    uid: transcriptUid(candidate),
    startTime: candidate.time,
    text: appliedText,
    textTs: candidate.textTs,
    revision,
    arrivalIndex: segment?.arrivalIndex ?? arrivalIndex,
  });
  return {
    text: rebuildSentenceTranscript(nextSegments),
    action: segment?.pendingFinal ? "replace-sentence-with-held-final" : segment ? "replace-sentence" : "create-sentence",
    segments: nextSegments,
    sentenceKey: key,
    sentenceStartTime: candidate.time,
    existingTextTs: segment?.textTs,
    textTs: candidate.textTs,
    pendingFinalTextTs: segment?.pendingFinal?.textTs,
    pendingFinalLength: segment?.pendingFinal?.text.length,
    heldFinalApplied: Boolean(segment?.pendingFinal),
    sentencesCount: nextSegments.size,
  };
}

type SttPhase =
  | "idle"
  | "preparing_rtc"
  | "joining_rtc"
  | "asr_bot_starting"
  | "ready_mic_off"
  | "draft_updating"
  | "error";

type SttResources = {
  rtcClient: any;
  micTrack: any;
  preparedSession: SttSessionPrepareResponse;
  sttSession: SttSessionStartResponse | null;
};

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
  onGlobalError,
}: {
  bro: BroCardModel;
  sessionId: string | null;
  summary: TaskSummary | null;
  onBack: () => void;
  onGlobalError?: (message: string | null) => void;
}) {
  const [sttPhase, setSttPhase] = useState<SttPhase>("idle");
  const [acceptedTranscript, setAcceptedTranscript] = useState("");
  const [draftSession, setDraftSession] = useState<DraftSession | null>(null);
  const [micActive, setMicActive] = useState(false);
  const resourcesRef = useRef<SttResources | null>(null);
  const submittedRef = useRef<Set<string>>(new Set());
  const acceptedTranscriptRef = useRef("");
  const sentenceSegmentsRef = useRef<Map<string, SentenceSegment>>(new Map());
  const transcriptArrivalIndexRef = useRef(0);
  const silenceCommitTimerRef = useRef<number | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const mountedRef = useRef(false);
  const generationRef = useRef(0);

  const clearSilenceCommitTimer = useCallback(() => {
    if (silenceCommitTimerRef.current === null) return;
    window.clearTimeout(silenceCommitTimerRef.current);
    silenceCommitTimerRef.current = null;
  }, []);

  const commitCurrentTranscript = useCallback(async (reason: "release" | "silence" | "final") => {
    clearSilenceCommitTimer();
    const draftRawText = acceptedTranscriptRef.current;
    if (!draftRawText) return;
    setSttPhase("draft_updating");
    console.debug("[BroDetail][STT] commit reason", reason);
    console.debug("[BroDetail][STT] draft raw text", draftRawText);

    if (submittedRef.current.has(draftRawText)) {
      setSttPhase("ready_mic_off");
      return;
    }
    submittedRef.current.add(draftRawText);

    if (sessionId) {
      try {
        const nextDraftSession = await submitDraftAsrTurn(sessionId, {
          raw_text: draftRawText,
          assigned_bro_id: bro.id,
        });
        setDraftSession(nextDraftSession as DraftSession);
        setSttPhase("ready_mic_off");
      } catch (error) {
        onGlobalError?.(error instanceof Error ? error.message : "Failed to update draft from transcript.");
        setSttPhase("error");
      }
    } else {
      setSttPhase("ready_mic_off");
    }
  }, [bro.id, clearSilenceCommitTimer, onGlobalError, sessionId]);

  const scheduleSilenceCommit = useCallback(() => {
    clearSilenceCommitTimer();
    silenceCommitTimerRef.current = window.setTimeout(() => {
      void commitCurrentTranscript("silence");
    }, STT_SILENCE_COMMIT_MS);
  }, [clearSilenceCommitTimer, commitCurrentTranscript]);

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
        onGlobalError?.(error instanceof Error ? error.message : "Failed to leave STT session.");
      }
    }
  }, [onGlobalError]);

  const handleTranscript = useCallback(async (payload: unknown) => {
    const parsed = extractTranscriptText(payload);
    if (!parsed) {
      console.debug("[BroDetail][STT] ignored payload", payload);
      return;
    }
    const arrivalIndex = ++transcriptArrivalIndexRef.current;
    const update = updateSentenceSegments(sentenceSegmentsRef.current, parsed, arrivalIndex);
    console.debug("[BroDetail][STT] received candidate", {
      segments: serializeTranscriptSegmentsForDebug(update.segments),
      displayText: update.text,
      words: parsed.words ?? [],
      protobuf: describeProtobufTranscriptPayload(payload),
    });
    if (
      update.action === "create-sentence"
      || update.action === "replace-sentence"
      || update.action === "replace-sentence-with-held-final"
      || update.action === "hold-final-fragment"
    ) {
      sentenceSegmentsRef.current = update.segments;
      if (update.text !== acceptedTranscriptRef.current) {
        acceptedTranscriptRef.current = update.text;
        setAcceptedTranscript(update.text);
      }
    } else {
      return;
    }
    if (parsed.final) {
      void commitCurrentTranscript("final");
      return;
    }
    scheduleSilenceCommit();
  }, [commitCurrentTranscript, scheduleSilenceCommit]);

  useEffect(() => {
    mountedRef.current = true;
    const generation = ++generationRef.current;
    let rtcClient: any | null = null;
    let micTrack: any | null = null;
    let preparedSession: SttSessionPrepareResponse | null = null;

    async function start() {
      if (!sessionId) return;
      setSttPhase("preparing_rtc");
      onGlobalError?.(null);
      try {
        preparedSession = await prepareSttSession({ synapse_session_id: sessionId, assigned_bro_id: bro.id });
        if (!mountedRef.current || generationRef.current !== generation) return;
        setSttPhase("joining_rtc");
        const { AgoraRTC } = await loadAgoraBrowserStack();
        rtcClient = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
        rtcClient.on?.("stream-message", (uid: string | number, payload: unknown) => {
          void handleTranscript(payload);
        });
        rtcClient.on?.("stream-message-error", (_uid: string | number, error: unknown) => {
          onGlobalError?.(error instanceof Error ? error.message : "Failed to receive STT transcript.");
        });
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
        if (!mountedRef.current || generationRef.current !== generation) return;
        setSttPhase("ready_mic_off");
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to start STT session.";
        if (mountedRef.current && generationRef.current === generation) {
          onGlobalError?.(message);
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
      clearSilenceCommitTimer();
      const resources = resourcesRef.current;
      resourcesRef.current = null;
      void leaveResources(resources);
    };
  }, [bro.id, clearSilenceCommitTimer, handleTranscript, leaveResources, onGlobalError, sessionId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const sttSessionId = resourcesRef.current?.sttSession?.stt_session_id;
      if (sttSessionId) {
        void heartbeatSttSession(sttSessionId).catch((error) => {
          if (mountedRef.current) {
            onGlobalError?.(error instanceof Error ? error.message : "Failed to heartbeat STT session.");
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
      setMicActive(enabled);
      if (!enabled) {
        void commitCurrentTranscript("release");
      }
    } catch (error) {
      onGlobalError?.(error instanceof Error ? error.message : "Failed to toggle microphone.");
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

  const readyForMic = sttPhase === "ready_mic_off" || sttPhase === "draft_updating";
  const capturing = micActive;
  const transcriptText = acceptedTranscript;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4 pt-3 md:px-6 md:pb-6 xl:px-8 xl:pb-8">
      <div className="glass-panel rounded-[24px] border border-white/75 px-4 py-3 md:px-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <BroPortrait bro={bro} active={bro.status === "busy"} talking={false} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">Bro detail</div>
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
            </div>
            <div className="flex flex-wrap items-center gap-2">
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
                {capturing ? "Release to finish" : "Hold to Talk"}
              </Button>
            </div>
          </div>

          <div className="mt-3 grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[0.85fr_1.15fr]">
            <div className="flex min-h-[260px] flex-col rounded-[24px] border border-white/75 bg-white/58 p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Live transcript</div>
              <div className="mt-3 min-h-0 flex-1 overflow-auto rounded-2xl bg-white/60 px-3 py-2 text-[14px] leading-7 text-foreground/78">
                <p>{transcriptText || "Latest transcript will appear here."}</p>
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
