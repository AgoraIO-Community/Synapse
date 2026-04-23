import { LoaderCircle, Mic, MicOff, PlayCircle, Radio, Square } from "lucide-react";
import { Button } from "../ui/button";
import type { BroCardModel } from "./types";

export function TopVoiceBar({
  bros,
  voicePhase,
  error,
  isMicMuted,
  transcriptCount,
  sessionId,
  onStart,
  onStop,
  onToggleMute,
}: {
  bros: BroCardModel[];
  voicePhase: "idle" | "loading" | "connected" | "error";
  error: string | null;
  isMicMuted: boolean;
  transcriptCount: number;
  sessionId: string | null;
  onStart: () => void;
  onStop: () => void;
  onToggleMute: () => void;
}) {
  const workingCount = bros.filter((bro) => bro.status === "busy").length;
  const title =
    voicePhase === "loading"
      ? "Starting voice session"
      : voicePhase === "connected"
        ? "Voice session live"
        : voicePhase === "error"
          ? "Voice session error"
          : "Voice ready";
  const subtitle =
    voicePhase === "loading"
      ? "Attaching live voice to the current Synapse session."
      : voicePhase === "connected"
        ? isMicMuted
          ? "Interaction memory is live. The microphone is currently muted."
          : "Interaction memory is live and updating from the active voice session."
        : voicePhase === "error"
          ? (error ?? "Voice startup failed. Retry when ready.")
          : "Press Start to attach a live voice session to the current Synapse session.";

  return (
    <div data-testid="top-voice-bar" className="border-b border-neutral-200 px-8 py-5 xl:px-10">
      <div className="flex items-center justify-between gap-6">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-400">Voice</div>
          <div className="mt-2 text-[18px] font-medium tracking-[-0.02em] text-neutral-950">{title}</div>
          <div className="mt-1 text-[13px] text-neutral-500">{subtitle}</div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-neutral-500">
            <div className="rounded-full border border-neutral-200 px-2.5 py-1">
              {workingCount}/{bros.length} Bros Working
            </div>
            <div className="rounded-full border border-neutral-200 px-2.5 py-1">
              {transcriptCount} transcript turns
            </div>
            {sessionId ? (
              <div className="rounded-full border border-neutral-200 px-2.5 py-1">
                Session {sessionId}
              </div>
            ) : null}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {voicePhase === "connected" ? (
            <>
              <Button
                data-testid="voice-session-stop"
                type="button"
                variant="secondary"
                size="sm"
                onClick={onStop}
                className="rounded-full bg-neutral-950 px-3 text-white hover:bg-neutral-800"
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
                className="rounded-full bg-white px-3 text-neutral-900 hover:bg-neutral-100"
              >
                {isMicMuted ? <Mic className="size-4" /> : <MicOff className="size-4" />}
                <span className="ml-1">{isMicMuted ? "Unmute" : "Mute"}</span>
              </Button>
            </>
          ) : (
            <Button
              data-testid="voice-session-start"
              type="button"
              variant="secondary"
              size="sm"
              onClick={onStart}
              className="rounded-full bg-neutral-950 px-3 text-white hover:bg-neutral-800"
            >
              {voicePhase === "loading" ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : voicePhase === "error" ? (
                <Radio className="size-4" />
              ) : (
                <PlayCircle className="size-4" />
              )}
              <span className="ml-1">{voicePhase === "error" ? "Retry" : "Start"}</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
