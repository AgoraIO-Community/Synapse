import { navItems } from "./data";

export type PageId = "Home" | "Bros" | "Nodes" | "Settings";

export function Sidebar({
  activePage,
  onNavigate,
}: {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}) {
  return (
    <aside
      data-testid="newbro-sidebar"
      className="flex h-full w-[228px] shrink-0 flex-col justify-between border-r border-neutral-200/90 bg-[#f7f5f0] px-5 py-5"
    >
      <div>
        <div className="mb-10 flex items-center gap-3 px-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-neutral-900 bg-neutral-950 text-[11px] font-semibold tracking-[0.24em] text-[#f7f5f0]">
            N
          </div>
          <div>
            <div className="text-[13px] font-semibold uppercase tracking-[0.18em] text-neutral-950">
              Newbro
            </div>
            <div className="text-[11px] text-neutral-500">Voice command center</div>
          </div>
        </div>

        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.label === activePage;
            return (
              <button
                key={item.label}
                type="button"
                onClick={() => onNavigate(item.label as PageId)}
                className={`group flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition ${
                  isActive
                    ? "bg-white text-neutral-950 ring-1 ring-neutral-200"
                    : "text-neutral-500 hover:bg-white/70 hover:text-neutral-800"
                }`}
              >
                <Icon className="h-4 w-4" strokeWidth={1.8} />
                <span className="text-[14px] font-medium">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white px-3 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-neutral-950 text-sm font-medium text-white">
            P
          </div>
          <div className="min-w-0">
            <div className="truncate text-[14px] font-medium text-neutral-900">Plutoless</div>
            <div className="truncate text-[12px] text-neutral-500">Central operator</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
