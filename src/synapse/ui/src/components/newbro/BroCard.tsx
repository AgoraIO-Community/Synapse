import { motion } from "framer-motion";
import { BroPortrait } from "./BroPortrait";
import type { BroCardModel } from "./types";

function liveStateNote(bro: BroCardModel) {
  if (bro.liveState === "live") {
    return bro.nodeName ? `Live on ${bro.nodeName}` : "Live runtime route";
  }
  if (bro.liveState === "offline") {
    return bro.nodeName ? `Waiting for ${bro.nodeName} to reconnect.` : "Waiting for executor node to reconnect.";
  }
  return "Needs node binding.";
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
      className="queue-card min-h-[132px] w-full rounded-[14px] border border-black/11 bg-white/43 px-3 py-4 text-left text-black backdrop-blur-sm transition duration-300 hover:-translate-y-0.5 hover:bg-white/62 sm:min-h-[150px] sm:px-5 sm:py-5"
    >
      <div className="flex min-w-0 items-start gap-2.5 sm:gap-4">
        <div className="shrink-0 scale-[0.82] origin-top-left sm:scale-100">
          <BroPortrait bro={bro} active={isBusy} talking={false} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-col gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <div className="newbro-condensed min-w-0 break-words text-[25px] leading-none sm:text-[30px]">{bro.name}</div>
                <div
                  className={`rounded-lg px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] ${
                    isBusy
                      ? "bg-[#ffe3d6] text-[#b33b15]"
                      : "bg-[#d5f5f2] text-[#087372]"
                  }`}
                >
                  {bro.status}
                </div>
              </div>
              <div className="mt-2 break-words text-[12px] leading-5 text-black/50">
                {bro.role} · {liveStateNote(bro)}
              </div>
            </div>

            <div className="rounded-[16px] border border-white/75 bg-[hsl(var(--paper))]/82 px-3 py-2.5 sm:rounded-[18px] sm:px-4 sm:py-3">
              <div className="serif-flow break-words text-[16px] leading-snug tracking-[0] text-foreground sm:text-[18px]">
                {bro.taskTitle}
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.button>
  );
}
