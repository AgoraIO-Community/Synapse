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
      className="relative z-20 flex w-full shrink-0 flex-col border-b border-black/10 bg-[#f4f3ee]/90 px-5 py-5 backdrop-blur lg:min-h-screen lg:w-[236px] lg:border-b-0 lg:border-r lg:border-black/10"
    >
      <div className="flex w-full flex-col gap-4 lg:block">
        <NewbroLogo />

        <nav className="flex flex-wrap items-center gap-x-5 gap-y-3 pb-1 text-sm lg:mt-20 lg:block lg:space-y-8 lg:pb-0 lg:text-[17px]">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.label === activePage;
            return (
              <button
                key={item.label}
                type="button"
                onClick={() => onNavigate(item.label as PageId)}
                className={`group flex shrink-0 items-center gap-2 text-left transition hover:text-[#ff4b16] lg:w-full lg:gap-4 ${
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
