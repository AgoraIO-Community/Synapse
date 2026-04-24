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
      className="flex w-full shrink-0 flex-col gap-6 border-b border-white/80 bg-white/42 px-4 py-4 backdrop-blur-xl lg:w-[236px] lg:border-b-0 lg:border-r lg:px-5 lg:py-6"
    >
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-3 px-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-full border border-primary/15 bg-primary/8 text-[11px] font-semibold tracking-[0.24em] text-primary">
            N
          </div>
          <div>
            <div className="text-[13px] font-semibold uppercase tracking-[0.2em] text-foreground">
              Newbro
            </div>
            <div className="text-[11px] text-muted-foreground">Voice command center</div>
          </div>
        </div>

        <nav className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.label === activePage;
            return (
              <button
                key={item.label}
                type="button"
                onClick={() => onNavigate(item.label as PageId)}
                className={`group flex shrink-0 items-center gap-3 rounded-full px-4 py-2.5 text-left transition lg:w-full lg:rounded-[20px] ${
                  isActive
                    ? "bg-white/88 text-foreground shadow-[0_18px_36px_-28px_rgba(47,108,243,0.28)] ring-1 ring-primary/10"
                    : "text-muted-foreground hover:bg-white/62 hover:text-foreground"
                }`}
              >
                <Icon className="h-4 w-4" strokeWidth={1.8} />
                <span className="text-[13px] font-medium">{item.label}</span>
                {isActive ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" /> : null}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="paper-panel rounded-[24px] border border-white/80 px-3 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-foreground text-sm font-medium text-white shadow-[0_12px_32px_-24px_rgba(15,23,42,0.45)]">
            O
          </div>
          <div className="min-w-0">
            <div className="truncate text-[14px] font-medium text-foreground">Operator Console</div>
            <div className="truncate text-[12px] text-muted-foreground">Shared control plane</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
