import { SectionHeader } from "./SectionHeader";
import { BroCard } from "./BroCard";
import type { BroCardModel } from "./types";

export function BrosPanel({
  bros,
  activeBroId,
  isTalking,
  voiceConnected,
  onBroPressStart,
  onBroPressEnd,
}: {
  bros: BroCardModel[];
  activeBroId: string | null;
  isTalking: boolean;
  voiceConnected: boolean;
  onBroPressStart: (broId: string) => void;
  onBroPressEnd: () => void;
}) {
  return (
    <div data-testid="bros-panel" className="w-full">
      <SectionHeader
        title="Available Bros"
        trailing={
          <div className="rounded-full border border-neutral-200 px-2.5 py-1 text-[11px] text-neutral-500">
            {bros.length} online
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {bros.map((bro) => {
          const isActive = bro.id === activeBroId;
          const talkingThis = isActive && isTalking;

          return (
            <BroCard
              key={bro.id}
              bro={bro}
              active={isActive}
              talking={talkingThis}
              voiceConnected={voiceConnected}
              onPressStart={onBroPressStart}
              onPressEnd={onBroPressEnd}
            />
          );
        })}
      </div>
    </div>
  );
}
