import { navItems } from "./data";
import { NewbroLogo } from "./visual";

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
      className="relative z-20 flex w-full shrink-0 flex-col border-b border-black/10 bg-[#f4f3ee]/90 px-4 py-4 backdrop-blur sm:px-5 sm:py-5 lg:min-h-screen lg:w-[236px] lg:border-b-0 lg:border-r lg:border-black/10"
    >
      <div className="flex w-full flex-col gap-3 lg:block">
        <NewbroLogo />

        <nav className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 pb-1 text-sm lg:mt-20 lg:block lg:space-y-8 lg:pb-0 lg:text-[17px]">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.label === activePage;
            return (
              <button
                key={item.label}
                type="button"
                onClick={() => onNavigate(item.label as PageId)}
                className={`group flex min-h-[36px] shrink-0 items-center gap-1.5 rounded-full px-1 text-left transition hover:text-[#ff4b16] lg:min-h-0 lg:w-full lg:gap-4 lg:rounded-none lg:px-0 ${
                  isActive
                    ? "font-semibold text-black"
                    : "text-black/80"
                }`}
              >
                <span className={`hidden h-1 w-4 rounded-full lg:block ${isActive ? "bg-[#ff4b16]" : "bg-transparent group-hover:bg-[#ff4b16]/35"}`} />
                <Icon className="h-4 w-4 lg:hidden" strokeWidth={1.8} />
                <span className="text-[13px] font-medium">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto hidden pb-4 lg:block">
        <div className="text-[#075f60]">
          <div className="text-4xl font-black leading-none">↗</div>
          <div className="newbro-condensed mt-1 text-[32px] leading-[0.82]">
            MAKE
            <br />
            WORK
            <br />
            NEW.
          </div>
          <div className="mt-4 h-1 w-28 -rotate-12 rounded-full bg-[#075f60]" />
        </div>
      </div>
    </aside>
  );
}
