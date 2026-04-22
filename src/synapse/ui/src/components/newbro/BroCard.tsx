import { motion } from "framer-motion";
import { BroPortrait } from "./BroPortrait";
import { BroProgress } from "./BroProgress";
import { TalkingBars } from "./TalkingBars";
import type { BroCardModel } from "./types";

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

  return (
    <motion.button
      data-testid={`bro-card-${bro.id}`}
      type="button"
      whileTap={{ scale: 0.992 }}
      onPointerDown={() => onPressStart(bro.id)}
      onPointerUp={onPressEnd}
      onPointerLeave={onPressEnd}
      onPointerCancel={onPressEnd}
      className={`min-h-[256px] w-full rounded-[24px] border px-5 py-4.5 text-left transition ${
        talking
          ? "border-neutral-900 bg-neutral-950 text-white"
          : active
            ? "border-neutral-300 bg-white text-neutral-950"
            : "border-neutral-200 bg-white text-neutral-900 hover:border-neutral-300 hover:bg-[#fffdfa]"
      }`}
    >
      <div className="flex items-start gap-4">
        <BroPortrait bro={bro} talking={talking} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <div className="text-[15px] font-medium tracking-[-0.02em]">{bro.name}</div>
                <div
                  className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] ${
                    talking
                      ? "border border-white/15 bg-white/10 text-white"
                      : isBusy
                        ? "border border-neutral-200 bg-neutral-100 text-neutral-700"
                        : "border border-neutral-200 bg-[#f6f5f2] text-neutral-600"
                  }`}
                >
                  {talking ? (voiceConnected ? "live" : "preview") : bro.status}
                </div>
              </div>
              <div className={`mt-1 text-[12px] ${talking ? "text-neutral-300" : "text-neutral-500"}`}>
                {bro.role}
              </div>
            </div>

            {talking ? (
              <div className="flex items-center gap-2 text-white">
                <TalkingBars active />
              </div>
            ) : null}
          </div>

          <BroProgress bro={bro} talking={talking} voiceConnected={voiceConnected} />
        </div>
      </div>
    </motion.button>
  );
}
