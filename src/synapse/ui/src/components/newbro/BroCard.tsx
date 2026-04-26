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
    return "bg-[#d5f5f2] text-[#087372]";
  }
  return "bg-[#ffe3d6] text-[#b33b15]";
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
      className="queue-card min-h-[210px] w-full rounded-[14px] border border-black/11 bg-white/43 px-5 py-5 text-left text-black backdrop-blur-sm transition duration-300 hover:-translate-y-0.5 hover:bg-white/62"
    >
      <div className="flex items-start gap-4">
        <BroPortrait bro={bro} active={isBusy} talking={false} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <div className="newbro-condensed text-[30px] leading-none">{bro.name}</div>
                <div
                  className={`rounded-lg px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] ${
                    isBusy
                      ? "bg-[#ffe3d6] text-[#b33b15]"
                      : "bg-[#d5f5f2] text-[#087372]"
                  }`}
                >
                  {bro.status}
                </div>
                <div
                  className={`rounded-lg px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] ${liveStateClasses(bro)}`}
                >
                  {liveStateLabel(bro)}
                </div>
              </div>
              <div className="mt-2 text-[12px] text-black/50">
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
