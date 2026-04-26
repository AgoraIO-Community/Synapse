import type { ReactNode } from "react";

export function SectionHeader({
  title,
  trailing,
}: {
  title: string;
  trailing?: ReactNode;
}) {
  return (
    <div className="mb-5 flex items-center justify-between gap-4 border-b border-black/10 pb-3">
      <div className="newbro-mono text-[10px] font-semibold uppercase tracking-[0.28em] text-black/45">
        {title}
      </div>
      {trailing ? <div>{trailing}</div> : null}
    </div>
  );
}
