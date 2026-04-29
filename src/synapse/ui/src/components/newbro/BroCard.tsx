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
      className="command-panel nb-bro-card min-h-[132px] w-full px-4 py-4 text-left transition duration-200 hover:-translate-y-px hover:border-[#d1d5db] sm:min-h-[150px] sm:px-5 sm:py-5"
    >
      <div className="flex min-w-0 items-start gap-3">
        <div className="shrink-0">
          <BroPortrait bro={bro} active={isBusy} talking={false} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-col gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <div className="nb-bro-card-title">{bro.name}</div>
                <div
                  className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    isBusy
                      ? "border-[#ff6a3d]/20 bg-[#fff0ec] text-[#ff6a3d]"
                      : "border-[#10b981]/20 bg-[#ecfdf5] text-[#059669]"
                  }`}
                >
                  {bro.status}
                </div>
              </div>
              <div className="mt-2 break-words text-[12px] leading-5 text-[#6b7280]">
                {bro.role} · {liveStateNote(bro)}
              </div>
            </div>

            <div className="command-field px-3 py-2.5 sm:px-4 sm:py-3">
              <div className="break-words text-[14px] leading-snug text-[#111827]">
                {bro.taskTitle}
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.button>
  );
}
