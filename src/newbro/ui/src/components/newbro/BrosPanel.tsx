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
    <div data-testid="bros-panel" className="nb-bros-panel">
      <div className="nb-bros-grid">
        {bros.map((bro) => (
          <BroCard key={bro.id} bro={bro} onClick={onBroClick} />
        ))}
      </div>
    </div>
  );
}
