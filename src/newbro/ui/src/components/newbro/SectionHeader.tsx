import type { ReactNode } from "react";

export function SectionHeader({
  title,
  trailing,
}: {
  title: string;
  trailing?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-col items-start justify-between gap-3 border-b border-[#e5e7eb] pb-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="command-label text-[#9ca3af]">
        {title}
      </div>
      {trailing ? <div className="w-full sm:w-auto">{trailing}</div> : null}
    </div>
  );
}
