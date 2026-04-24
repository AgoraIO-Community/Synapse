import { LoaderCircle, Mic, MicOff, PlayCircle, Radio, Square } from "lucide-react";
import { SectionHeader } from "./SectionHeader";
import { BroCard } from "./BroCard";
import type { BroCardModel } from "./types";
import { Button } from "../ui/button";

export function BrosPanel({
  bros,
  pressedBroId,
  isTalking,
  voiceConnected,
  voicePhase,
  voiceError,
  isMicMuted,
  messageCount,
  sessionId,
  onStart,
  onStop,
  onToggleMute,
  onBroPressStart,
  onBroPressEnd,
}: {
  bros: BroCardModel[];
  pressedBroId: string | null;
  isTalking: boolean;
  voiceConnected: boolean;
  voicePhase: "idle" | "loading" | "connected" | "error";
  voiceError: string | null;
  isMicMuted: boolean;
  messageCount: number;
  sessionId: string | null;
  onStart: () => void;
  onStop: () => void;
  onToggleMute: () => void;
  onBroPressStart: (broId: string) => void;
  onBroPressEnd: () => void;
}) {
  const liveCount = bros.filter((bro) => bro.liveState === "live").length;
  const statusChipClass =
    voicePhase === "connected"
      ? "border-primary/15 bg-primary/10 text-primary"
      : voicePhase === "loading"
        ? "border-primary/12 bg-white/82 text-primary"
        : voicePhase === "error"
          ? "border-[#8d5a62]/12 bg-white/82 text-[#8d5a62]"
          : "border-border/70 bg-white/78 text-muted-foreground";
  const statusLabel =
    voicePhase === "connected"
      ? isMicMuted
        ? "Muted"
        : "Live"
      : voicePhase === "loading"
        ? "Starting"
        : voicePhase === "error"
          ? "Error"
          : "Ready";

  return (
    <div data-testid="bros-panel" className="w-full">
      <SectionHeader
        title="Available Bros"
        trailing={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <div className="rounded-full border border-white/80 bg-white/74 px-3 py-1 text-[11px] text-muted-foreground">
              {liveCount} live
            </div>
            {sessionId ? (
              <div className="rounded-full border border-white/80 bg-white/74 px-3 py-1 text-[11px] text-muted-foreground">
                Session {sessionId}
              </div>
            ) : null}
            <div className="sr-only">
              <div className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${statusChipClass}`}>
                {statusLabel}
              </div>
              <div>{messageCount} turns</div>
              {voicePhase === "connected" ? (
                <>
                  <Button
                    data-testid="voice-session-stop"
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onStop}
                    className="rounded-full bg-white/70 px-3 text-foreground backdrop-blur-md hover:bg-white"
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
                    className="rounded-full px-3"
                  >
                    {isMicMuted ? <Mic className="size-4" /> : <MicOff className="size-4" />}
                    <span className="ml-1">{isMicMuted ? "Unmute" : "Mute"}</span>
                  </Button>
                </>
              ) : (
                <Button
                  data-testid="voice-session-start"
                  type="button"
                  variant={voicePhase === "error" ? "outline" : "default"}
                  size="sm"
                  onClick={onStart}
                  className="rounded-full px-3"
                  title={voiceError ?? undefined}
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
        }
      />

      <div className="grid grid-cols-1 gap-4">
        {bros.map((bro) => {
          const isActive = bro.id === pressedBroId;
          const talkingThis = isActive && isTalking;

          return (
            <BroCard
              key={bro.id}
              bro={bro}
              active={isActive}
              talking={talkingThis}
              voiceConnected={voiceConnected}
              onPressStart={onBroPressStart}
              onPressEnd={onBroPressEnd}
            />
          );
        })}
      </div>
    </div>
  );
}
