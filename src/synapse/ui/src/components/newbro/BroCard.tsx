import { motion } from "framer-motion";
import { BroPortrait } from "./BroPortrait";
import { BroProgress } from "./BroProgress";
import { TalkingBars } from "./TalkingBars";
import type { BroCardModel } from "./types";

function liveStateLabel(bro: BroCardModel) {
  if (bro.liveState === "live") {
    return "live";
  }
  if (bro.liveState === "offline") {
    return "bound offline";
  }
  return "unbound";
}

function liveStateClasses(bro: BroCardModel, talking: boolean) {
  if (talking) {
    return "border border-primary/15 bg-primary/10 text-primary";
  }
  if (bro.liveState === "live") {
    return "border border-primary/12 bg-primary/10 text-primary";
  }
  return "border border-border/70 bg-[hsl(var(--paper))] text-muted-foreground";
}

export function BroCard({
  bro,
  active,
  talking,
  voiceConnected,
  onPressStart,
  onPressEnd,
}: {
  bro: BroCardModel;
  active: boolean;
  talking: boolean;
  voiceConnected: boolean;
  onPressStart: (broId: string) => void;
  onPressEnd: () => void;
}) {
  const isBusy = bro.status === "busy";
  const showActivity = active || talking;

  return (
    <motion.button
      data-testid={`bro-card-${bro.id}`}
      type="button"
      aria-pressed={active}
      whileTap={{ scale: 0.997 }}
      onPointerDown={() => onPressStart(bro.id)}
      onPointerUp={onPressEnd}
      onPointerLeave={onPressEnd}
      onPointerCancel={onPressEnd}
      className={`min-h-[250px] w-full rounded-[28px] border px-5 py-5 text-left transition duration-300 backdrop-blur-xl ${
        talking
          ? "border-primary/15 bg-[linear-gradient(180deg,rgba(237,244,255,0.97),rgba(255,255,255,0.92))] text-foreground shadow-[0_28px_64px_-46px_rgba(47,108,243,0.34)]"
          : active
            ? "border-primary/15 bg-white/88 text-foreground shadow-[0_24px_58px_-44px_rgba(47,108,243,0.28)] ring-1 ring-primary/8"
            : "border-white/80 bg-white/62 text-foreground shadow-[0_18px_46px_-42px_rgba(15,23,42,0.18)] hover:border-white hover:bg-white/82"
      }`}
    >
      <div className="flex items-start gap-4">
        <BroPortrait bro={bro} active={showActivity} talking={talking} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <div className="serif-flow text-[22px] leading-none tracking-[-0.04em]">{bro.name}</div>
                <div
                  className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] ${
                    showActivity
                      ? "border border-primary/15 bg-primary/10 text-primary"
                      : isBusy
                        ? "border border-primary/12 bg-primary/10 text-primary"
                        : "border border-border/70 bg-[hsl(var(--paper))] text-muted-foreground"
                  }`}
                >
                  {showActivity ? (voiceConnected && talking ? "mic on" : "preview") : bro.status}
                </div>
                <div
                  className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] ${liveStateClasses(bro, talking)}`}
                >
                  {liveStateLabel(bro)}
                </div>
              </div>
              <div className="mt-2 text-[12px] text-muted-foreground">
                {bro.nodeName ? `${bro.role} · ${bro.nodeName}` : `${bro.role} · needs binding`}
              </div>
            </div>

            {showActivity ? (
              <div className="flex items-center gap-2 text-primary">
                <TalkingBars active />
              </div>
            ) : null}
          </div>

          <BroProgress bro={bro} talking={talking} />
        </div>
      </div>
    </motion.button>
  );
}
