import {
  CircleAlert,
  LoaderCircle,
  Mic,
  MicOff,
  PlayCircle,
  Radio,
  RotateCcw,
  Square,
  Volume2,
  Waves,
} from "lucide-react";
import type { ConnectorActivateResponse } from "../lib/connector-client";
import { Button } from "./ui/button";
import { cn } from "../lib/utils";

export type VoiceModePhase = "idle" | "loading" | "connected" | "error";

export type VoiceTranscriptTurn = {
  turn_id?: string | number;
  uid?: string | number;
  text?: string;
  status?: string;
  metadata?: Record<string, unknown>;
};

function describePhase(phase: VoiceModePhase) {
  if (phase === "loading") {
    return "Starting voice session";
  }
  if (phase === "connected") {
    return "Voice session live";
  }
  if (phase === "error") {
    return "Voice session error";
  }
  return "Voice ready";
}

function formatTime(value: string | null) {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(
    2,
    "0",
  )}:${String(date.getSeconds()).padStart(2, "0")}`;
}

function normalizeSpeakerId(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return null;
  }
  const raw = String(value).trim();
  return raw.length > 0 ? raw : null;
}

function resolveTranscriptSpeakerLabel(
  item: VoiceTranscriptTurn,
  activeSession: ConnectorActivateResponse | null,
) {
  const metadata = item.metadata;
  const metadataObject =
    metadata && typeof metadata.object === "string" ? metadata.object.toLowerCase() : null;
  if (metadataObject?.includes("agent")) {
    return "NewBro";
  }
  if (metadataObject?.includes("user")) {
    return "Me";
  }

  const transcriptUid = normalizeSpeakerId(item.uid);
  const agentUid = normalizeSpeakerId(activeSession?.agent.uid);
  const userUid = normalizeSpeakerId(activeSession?.uid);
  const diagnosticUserUid = normalizeSpeakerId(activeSession?.diagnostics.rtc_uid);

  if (transcriptUid && agentUid && transcriptUid === agentUid) {
    return "NewBro";
  }
  if (
    transcriptUid &&
    ((userUid && transcriptUid === userUid) ||
      (diagnosticUserUid && transcriptUid === diagnosticUserUid))
  ) {
    return "Me";
  }

  return "Speaker";
}

export function VoiceModePanel({
  phase,
  agentState,
  activeSession,
  transcript,
  error,
  lastTranscriptUpdateAt,
  lastToolkitMessage,
  isMicMuted,
  onStart,
  onStop,
  onToggleMute,
  onRetry,
}: {
  phase: VoiceModePhase;
  agentState: string;
  activeSession: ConnectorActivateResponse | null;
  transcript: VoiceTranscriptTurn[];
  error: string | null;
  lastTranscriptUpdateAt: string | null;
  lastToolkitMessage: string | null;
  isMicMuted: boolean;
  onStart: () => void;
  onStop: () => void;
  onToggleMute: () => void;
  onRetry: () => void;
}) {
  const transcriptItems = transcript.filter((item) => Boolean(item.text?.trim()));
  const hasActiveSession = phase === "connected" && activeSession !== null;

  return (
    <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-5 py-8">
      <div className="rounded-[1.3rem] border border-[rgba(214,255,100,0.12)] bg-[linear-gradient(180deg,rgba(20,22,26,0.9),rgba(28,31,36,0.86))] px-4 py-4 text-white shadow-[0_22px_48px_-30px_rgba(0,0,0,0.55)] backdrop-blur-xl sm:px-5">
        <div className="flex flex-wrap items-center gap-2.5">
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[0.68rem] font-bold uppercase tracking-[0.18em]",
              phase === "connected"
                ? "bg-[#d6ff64]/14 text-[#d6ff64]"
                : phase === "error"
                  ? "bg-rose-400/10 text-rose-200"
                  : "bg-white/8 text-white/75",
            )}
          >
            {phase === "loading" ? (
              <LoaderCircle className="size-3.5 animate-spin" />
            ) : phase === "connected" ? (
              <Radio className="size-3.5" />
            ) : phase === "error" ? (
              <CircleAlert className="size-3.5" />
            ) : (
              <Mic className="size-3.5" />
            )}
            <span>{describePhase(phase)}</span>
          </span>

          {activeSession ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/6 px-3 py-1.5 text-[0.68rem] font-semibold tracking-[0.08em] text-white/68">
              <Volume2 className="size-3.5 text-[#d6ff64]" />
              <span>{activeSession.channel_name}</span>
            </span>
          ) : null}

          <div className="ml-auto flex items-center gap-2">
            {phase === "connected" ? (
              <>
                <Button
                  data-testid="voice-session-stop"
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={onStop}
                  className="rounded-full bg-white px-3 text-[#111612] hover:bg-white/90"
                >
                  <Square className="size-4 fill-current" />
                  <span className="ml-1">Stop</span>
                </Button>
                <Button
                  data-testid="voice-session-mic-toggle"
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={onToggleMute}
                  className="rounded-full bg-white/8 px-3 text-white hover:bg-white/12"
                >
                  {isMicMuted ? <Mic className="size-4" /> : <MicOff className="size-4" />}
                  <span className="ml-1">{isMicMuted ? "Unmute" : "Mute"}</span>
                </Button>
              </>
            ) : activeSession ? (
              <Button
                data-testid="voice-session-retry-stop"
                type="button"
                variant="secondary"
                size="sm"
                onClick={onRetry}
                className="rounded-full bg-white/8 px-3 text-white hover:bg-white/12"
              >
                <RotateCcw className="size-4" />
                <span className="ml-1">Retry stop</span>
              </Button>
            ) : (
              <>
                <Button
                  data-testid="voice-session-start"
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={onStart}
                  className="rounded-full bg-[#d6ff64] px-3 text-[#14180c] shadow-[0_12px_24px_-14px_rgba(214,255,100,0.88)] hover:bg-[#e0ff84]"
                >
                  {phase === "loading" ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <PlayCircle className="size-4" />
                  )}
                  <span className="ml-1">Start</span>
                </Button>
                {phase === "error" ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={onRetry}
                    className="rounded-full bg-white/8 px-3 text-white hover:bg-white/12"
                  >
                    <RotateCcw className="size-4" />
                    <span className="ml-1">Retry</span>
                  </Button>
                ) : null}
              </>
            )}
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-[0.95rem] bg-white/5 px-4 py-3">
            <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
              Agent state
            </p>
            <p className="mt-2 text-sm leading-5 text-white/78">{agentState}</p>
          </div>
          <div className="rounded-[0.95rem] bg-white/5 px-4 py-3">
            <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
              Synapse session
            </p>
            <p className="mt-2 break-all text-sm leading-5 text-white/78">
              {activeSession?.synapse_session_id ?? "Not connected"}
            </p>
          </div>
          <div className="rounded-[0.95rem] bg-white/5 px-4 py-3">
            <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
              Microphone
            </p>
            <p className="mt-2 text-sm leading-5 text-white/78">
              {!hasActiveSession ? "Unavailable until Start" : isMicMuted ? "Muted" : "Live"}
            </p>
          </div>
          <div className="rounded-[0.95rem] bg-white/5 px-4 py-3">
            <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
              Last transcript update
            </p>
            <p className="mt-2 text-sm leading-5 text-white/78">{formatTime(lastTranscriptUpdateAt)}</p>
          </div>
          <div className="rounded-[0.95rem] bg-white/5 px-4 py-3">
            <p className="text-[0.62rem] font-bold uppercase tracking-[0.18em] text-white/42">
              Toolkit log
            </p>
            <p className="mt-2 text-sm leading-5 text-white/78">
              {lastToolkitMessage ?? "No toolkit message yet."}
            </p>
          </div>
        </div>

        {error ? (
          <div className="mt-3 rounded-[1rem] border border-rose-400/14 bg-rose-400/8 px-3 py-2.5 text-sm leading-5 text-rose-100">
            {error}
          </div>
        ) : null}
      </div>

      <div
        data-testid="voice-mode-transcript-feed"
        className="rounded-[1.3rem] border border-white/65 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(250,250,248,0.76))] px-4 py-4 text-[#1f2521] shadow-[0_22px_48px_-32px_rgba(15,23,42,0.18)] backdrop-blur-xl sm:px-5"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-2 text-[0.66rem] font-bold uppercase tracking-[0.18em] text-[#65705a]">
              <Waves className="size-3.5 text-[#7e9862]" />
              <span>Voice Transcript</span>
            </div>
            <h3 className="mt-2 font-['Noto_Sans_SC','Noto_Sans','Geist_Variable',sans-serif] text-[1.65rem] font-bold tracking-[-0.05em] text-[#1f2521]">
              Live channel transcript
            </h3>
          </div>
          <span className="rounded-full bg-[#1d2321] px-3 py-1 text-[0.68rem] font-bold uppercase tracking-[0.16em] text-[#d6ff64]">
            {transcriptItems.length} turns
          </span>
        </div>

        <div className="mt-5 space-y-3">
          {phase === "loading" ? (
            <div className="rounded-[1rem] border border-dashed border-[#d2d9cf] bg-white/70 px-4 py-4 text-sm leading-6 text-[#5e6761]">
              Connecting Agora RTC, RTM, toolkit, and the bound Synapse session.
            </div>
          ) : phase === "idle" ? (
            <div className="rounded-[1rem] border border-dashed border-[#d2d9cf] bg-white/70 px-4 py-4 text-sm leading-6 text-[#5e6761]">
              Voice mode is selected, but no live session is running yet. Press Start to begin voice interaction and bind the workbench to the live voice session.
            </div>
          ) : transcriptItems.length === 0 ? (
            <div className="rounded-[1rem] border border-dashed border-[#d2d9cf] bg-white/70 px-4 py-4 text-sm leading-6 text-[#5e6761]">
              The voice session is live. Speak into the microphone and transcript turns will appear here.
            </div>
          ) : (
            transcriptItems.map((item, index) => (
              <div
                key={`${item.turn_id ?? "turn"}-${item.uid ?? "uid"}-${index}`}
                className="rounded-[1rem] border border-[#e4e8e0] bg-white px-4 py-4 shadow-[0_16px_34px_-28px_rgba(15,23,42,0.14)]"
              >
                <div className="mb-2 flex items-center gap-3 text-[0.66rem] font-bold uppercase tracking-[0.16em] text-[#7a847d]">
                  <span>{resolveTranscriptSpeakerLabel(item, activeSession)}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-6 text-[#1f2521]">{item.text}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
