import type { BroCardModel } from "./types";

export function BroProgress({
  bro,
  talking,
}: {
  bro: BroCardModel;
  talking: boolean;
}) {
  const isBusy = bro.status === "busy";

  if (!isBusy) {
    return (
      <div
        className={`mt-4 rounded-[18px] border px-3 py-3 ${
          talking ? "border-white/10 bg-white/5" : "border-neutral-200 bg-[#fbfaf7]"
        }`}
      >
        <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Current state</div>
        <div className={`mt-2 text-[13px] font-medium ${talking ? "text-white" : "text-neutral-800"}`}>
          {bro.taskTitle}
        </div>
        <div className={`mt-1 text-[12px] leading-5 ${talking ? "text-neutral-300" : "text-neutral-500"}`}>
          {bro.idleNote}
        </div>

        <div className="mt-3 space-y-2">
          {bro.progressDetails.map((detail) => (
            <div
              key={detail}
              className={`flex items-start gap-2 text-[12px] leading-5 ${
                talking ? "text-neutral-300" : "text-neutral-500"
              }`}
            >
              <div className={`mt-[6px] h-1.5 w-1.5 rounded-full ${talking ? "bg-white/50" : "bg-neutral-300"}`} />
              <div>{detail}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`mt-4 rounded-[18px] border px-3 py-3 ${
        talking ? "border-white/10 bg-white/5" : "border-neutral-200 bg-[#fbfaf7]"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Current task</div>
        <div className={`text-[11px] ${talking ? "text-neutral-300" : "text-neutral-400"}`}>
          {bro.progressLabel}
        </div>
      </div>

      <div className={`mt-2 text-[13px] font-medium ${talking ? "text-white" : "text-neutral-800"}`}>
        {bro.taskTitle}
      </div>

      <div className={`mt-2 h-1.5 w-full overflow-hidden rounded-full ${talking ? "bg-white/10" : "bg-neutral-200"}`}>
        <div
          className={`h-full rounded-full ${talking ? "bg-white/75" : "bg-emerald-500"}`}
          style={{ width: `${bro.progress}%` }}
        />
      </div>

      <div className="mt-3 space-y-2">
        {bro.progressDetails.map((detail) => (
          <div
            key={detail}
            className={`flex items-start gap-2 text-[12px] leading-5 ${
              talking ? "text-neutral-300" : "text-neutral-500"
            }`}
          >
            <div className={`mt-[6px] h-1.5 w-1.5 rounded-full ${talking ? "bg-white/50" : "bg-neutral-300"}`} />
            <div>{detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
