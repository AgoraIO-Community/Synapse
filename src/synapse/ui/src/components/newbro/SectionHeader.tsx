import type { ReactNode } from "react";

export function SectionHeader({
  title,
  trailing,
}: {
  title: string;
  trailing?: ReactNode;
}) {
  return (
    <div className="mb-5 flex items-center justify-between gap-4 border-b border-border/55 pb-3">
      <div className="text-[10px] font-medium uppercase tracking-[0.28em] text-muted-foreground">
        {title}
      </div>
      {trailing ? <div>{trailing}</div> : null}
    </div>
  );
}
