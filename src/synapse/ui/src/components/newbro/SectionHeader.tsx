import type { ReactNode } from "react";

export function SectionHeader({
  title,
  trailing,
}: {
  title: string;
  trailing?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-center justify-between gap-4">
      <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-400">{title}</div>
      {trailing ? <div>{trailing}</div> : null}
    </div>
  );
}
