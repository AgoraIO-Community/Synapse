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
        className={`mt-5 rounded-[22px] border px-4 py-4 ${
          talking ? "border-primary/12 bg-primary/6" : "border-white/80 bg-[hsl(var(--paper))]"
        }`}
      >
        <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground">Current state</div>
        <div className={`serif-flow mt-3 text-[21px] leading-tight tracking-[-0.03em] ${talking ? "text-primary" : "text-foreground"}`}>
          {bro.taskTitle}
        </div>
        <div className="mt-2 text-[12px] leading-6 text-muted-foreground">
          {bro.idleNote}
        </div>

        <div className="mt-4 space-y-2.5">
          {bro.progressDetails.map((detail) => (
            <div
              key={detail}
              className="flex items-start gap-2.5 text-[12px] leading-6 text-muted-foreground"
            >
              <div className={`mt-[9px] h-1.5 w-1.5 rounded-full ${talking ? "bg-primary/65" : "bg-muted-foreground/35"}`} />
              <div>{detail}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`mt-5 rounded-[22px] border px-4 py-4 ${
        talking ? "border-primary/12 bg-primary/6" : "border-white/80 bg-[hsl(var(--paper))]"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-[10px] uppercase tracking-[0.22em] text-muted-foreground">Current task</div>
        <div className={`text-[11px] ${talking ? "text-primary" : "text-muted-foreground"}`}>
          {bro.progressLabel}
        </div>
      </div>

      <div className={`serif-flow mt-3 text-[21px] leading-tight tracking-[-0.03em] ${talking ? "text-primary" : "text-foreground"}`}>
        {bro.taskTitle}
      </div>

      <div className={`mt-4 h-1.5 w-full overflow-hidden rounded-full ${talking ? "bg-primary/14" : "bg-border/70"}`}>
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${bro.progress}%` }}
        />
      </div>

      <div className="mt-4 space-y-2.5">
        {bro.progressDetails.map((detail) => (
          <div
            key={detail}
            className="flex items-start gap-2.5 text-[12px] leading-6 text-muted-foreground"
          >
            <div className={`mt-[9px] h-1.5 w-1.5 rounded-full ${talking ? "bg-primary/65" : "bg-muted-foreground/35"}`} />
            <div>{detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
