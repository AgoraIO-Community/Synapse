import type { BroCardModel } from "./types";

export function BroProgress({
  bro,
  talking,
  voiceConnected,
}: {
  bro: BroCardModel;
  talking: boolean;
  voiceConnected: boolean;
}) {
  const isBusy = bro.status === "busy";
  const talkingTitle = voiceConnected ? `Talking to ${bro.name}` : `Previewing ${bro.name}`;
  const talkingDetail = voiceConnected
    ? "Mic unmuted. Release to exit talk mode."
    : "Hold state is visual only. Start voice in the top bar for a live session.";

  if (!isBusy) {
    return (
      <div
        className={`mt-4 rounded-[18px] border px-3 py-3 ${
          talking ? "border-white/10 bg-white/5" : "border-neutral-200 bg-[#fbfaf7]"
        }`}
      >
        <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">Current state</div>
        <div className={`mt-2 text-[13px] font-medium ${talking ? "text-white" : "text-neutral-800"}`}>
          {talking ? talkingTitle : bro.taskTitle}
        </div>
        <div
          className={`mt-1 text-[12px] leading-5 ${
            talking ? "text-neutral-300" : "text-neutral-500"
          }`}
        >
          {talking ? talkingDetail : bro.idleNote}
        </div>
        {!talking ? (
          <div className="mt-3 space-y-2">
            {bro.progressDetails.map((detail) => (
              <div key={detail} className="flex items-start gap-2 text-[12px] leading-5 text-neutral-500">
                <div className="mt-[6px] h-1.5 w-1.5 rounded-full bg-neutral-300" />
                <div>{detail}</div>
              </div>
            ))}
          </div>
        ) : null}
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
        <div className="text-[11px] uppercase tracking-[0.18em] text-neutral-400">
          {talking ? (voiceConnected ? "Talk mode" : "Preview") : "Current task"}
        </div>
        {!talking ? <div className="text-[11px] text-neutral-400">{bro.progressLabel}</div> : null}
      </div>

      <div className={`mt-2 text-[13px] font-medium ${talking ? "text-white" : "text-neutral-800"}`}>
        {talking ? talkingTitle : bro.taskTitle}
      </div>

      <div
        className={`mt-2 h-1.5 w-full overflow-hidden rounded-full ${
          talking ? "bg-white/10" : "bg-neutral-200"
        }`}
      >
        <div
          className={`h-full rounded-full ${talking ? "bg-white/75" : "bg-emerald-500"}`}
          style={{ width: `${bro.progress}%` }}
        />
      </div>

      <div className="mt-3 space-y-2">
        {(talking ? [talkingDetail] : bro.progressDetails).map((detail) => (
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
