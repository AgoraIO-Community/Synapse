import { useState } from "react";
import { Menu } from "lucide-react";
import { navItems } from "./data";
import { NewbroLogo } from "./visual";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "../ui/sheet";

export type PageId = "Home" | "Bros" | "Nodes" | "Settings";

export function Sidebar({
  activePage,
  onNavigate,
}: {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  function navigate(page: PageId) {
    onNavigate(page);
    setDrawerOpen(false);
  }

  const nav = (
    <nav className="flex w-full flex-col gap-2 text-[16px] lg:mt-20 lg:gap-0 lg:space-y-8 lg:text-[17px]">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = item.label === activePage;
        return (
          <button
            key={item.label}
            type="button"
            onClick={() => navigate(item.label as PageId)}
            className={`group flex min-h-[48px] w-full items-center gap-3 rounded-[14px] px-3 text-left transition hover:text-[#ff4b16] lg:min-h-0 lg:gap-4 lg:rounded-none lg:px-0 ${
              isActive
                ? "bg-white/70 font-semibold text-black lg:bg-transparent"
                : "text-black/80"
            }`}
          >
            <span className={`hidden h-1 w-4 rounded-full lg:block ${isActive ? "bg-[#ff4b16]" : "bg-transparent group-hover:bg-[#ff4b16]/35"}`} />
            <Icon className="h-4 w-4 shrink-0" strokeWidth={1.8} />
            <span className="text-[15px] font-medium lg:text-[13px]">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );

  return (
    <>
      <header
        data-testid="newbro-mobile-header"
        className="sticky top-0 z-40 flex min-h-[64px] w-full items-center justify-between border-b border-black/10 bg-[#f4f3ee]/95 px-4 py-3 backdrop-blur lg:hidden"
      >
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetTrigger asChild>
            <button
              type="button"
              aria-label="Open navigation menu"
              className="grid min-h-[44px] min-w-[44px] place-items-center rounded-full border border-black/12 bg-white/62 text-black transition hover:bg-white"
            >
              <Menu className="h-5 w-5" strokeWidth={1.9} />
            </button>
          </SheetTrigger>
          <SheetContent
            side="left"
            className="w-[min(86vw,340px)] gap-6 border-black/10 bg-[#f4f3ee] px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-5"
          >
            <SheetHeader className="pr-10">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <SheetDescription className="sr-only">
                Choose a Newbro workspace page.
              </SheetDescription>
              <NewbroLogo />
            </SheetHeader>
            {nav}
            <div className="mt-auto rounded-[18px] border border-black/10 bg-white/50 px-4 py-4 text-[#075f60]">
              <div className="newbro-condensed text-[28px] leading-[0.82]">
                MAKE WORK NEW.
              </div>
            </div>
          </SheetContent>
        </Sheet>
        <NewbroLogo />
      </header>

      <aside
        data-testid="newbro-sidebar"
        className="relative z-20 hidden w-full shrink-0 flex-col border-b border-black/10 bg-[#f4f3ee]/90 px-4 py-4 backdrop-blur sm:px-5 sm:py-5 lg:flex lg:min-h-dvh lg:w-[236px] lg:border-b-0 lg:border-r lg:border-black/10"
      >
        <div className="flex w-full flex-col gap-3 lg:block">
          <NewbroLogo />
          {nav}
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
    </>
  );
}
