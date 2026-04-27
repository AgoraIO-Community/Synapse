import type { ReactNode } from "react";

export function SectionHeader({
  title,
  trailing,
}: {
  title: string;
  trailing?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-col items-start justify-between gap-3 border-b border-black/10 pb-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="newbro-mono text-[10px] font-semibold uppercase tracking-[0.28em] text-black/45">
        {title}
      </div>
      {trailing ? <div className="w-full sm:w-auto">{trailing}</div> : null}
    </div>
  );
}
