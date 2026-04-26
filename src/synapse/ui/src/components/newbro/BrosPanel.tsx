import { BroCard } from "./BroCard";
import type { BroCardModel } from "./types";

export function BrosPanel({
  bros,
  sessionId: _sessionId,
  onBroClick,
}: {
  bros: BroCardModel[];
  sessionId: string | null;
  onBroClick?: (broId: string) => void;
}) {
  return (
    <div data-testid="bros-panel" className="w-full">
      <div className="mb-5 flex items-center justify-between gap-4 border-b border-black/10 pb-3">
        <div>
          <div className="newbro-mono text-[10px] font-semibold uppercase tracking-[0.28em] text-black/45">
            Available Bros
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {bros.map((bro) => (
          <BroCard key={bro.id} bro={bro} onClick={onBroClick} />
        ))}
      </div>
    </div>
  );
}
