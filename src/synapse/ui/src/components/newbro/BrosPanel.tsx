import { SectionHeader } from "./SectionHeader";
import { BroCard } from "./BroCard";
import type { BroCardModel } from "./types";

export function BrosPanel({
  bros,
  sessionId,
  onBroClick,
}: {
  bros: BroCardModel[];
  sessionId: string | null;
  onBroClick?: (broId: string) => void;
}) {
  const liveCount = bros.filter((bro) => bro.liveState === "live").length;

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
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4">
        {bros.map((bro) => (
          <BroCard key={bro.id} bro={bro} onClick={onBroClick} />
        ))}
      </div>
    </div>
  );
}
