import { motion } from "framer-motion";
import { BroPortrait } from "./BroPortrait";
import { BroProgress } from "./BroProgress";
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

function liveStateClasses(bro: BroCardModel) {
  if (bro.liveState === "live") {
    return "border border-primary/12 bg-primary/10 text-primary";
  }
  return "border border-border/70 bg-[hsl(var(--paper))] text-muted-foreground";
}

export function BroCard({
  bro,
  onClick,
}: {
  bro: BroCardModel;
  onClick?: (broId: string) => void;
}) {
  const isBusy = bro.status === "busy";

  return (
    <motion.button
      data-testid={`bro-card-${bro.id}`}
      type="button"
      whileTap={{ scale: 0.997 }}
      onClick={() => onClick?.(bro.id)}
      className="min-h-[250px] w-full rounded-[28px] border border-white/80 bg-white/62 px-5 py-5 text-left text-foreground shadow-[0_18px_46px_-42px_rgba(15,23,42,0.18)] backdrop-blur-xl transition duration-300 hover:border-white hover:bg-white/82"
    >
      <div className="flex items-start gap-4">
        <BroPortrait bro={bro} active={isBusy} talking={false} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <div className="serif-flow text-[22px] leading-none tracking-[-0.04em]">{bro.name}</div>
                <div
                  className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] ${
                    isBusy
                      ? "border border-primary/12 bg-primary/10 text-primary"
                      : "border border-border/70 bg-[hsl(var(--paper))] text-muted-foreground"
                  }`}
                >
                  {bro.status}
                </div>
                <div
                  className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] ${liveStateClasses(bro)}`}
                >
                  {liveStateLabel(bro)}
                </div>
              </div>
              <div className="mt-2 text-[12px] text-muted-foreground">
                {bro.nodeName ? `${bro.role} · ${bro.nodeName}` : `${bro.role} · needs binding`}
              </div>
            </div>
          </div>

          <BroProgress bro={bro} talking={false} />
        </div>
      </div>
    </motion.button>
  );
}
