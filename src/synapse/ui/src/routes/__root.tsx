/// <reference types="vite/client" />
import { HeadContent, Outlet, createRootRoute } from "@tanstack/react-router";
import type { DetailedHTMLProps, LinkHTMLAttributes } from "react";
import { DefaultCatchBoundary } from "../components/DefaultCatchBoundary";
import { NotFound } from "../components/NotFound";
import { normalizeSessionIdParam } from "../lib/session-url";
import { NewbroShellProvider } from "../NewbroShell";

const externalFontLinks: Array<
  DetailedHTMLProps<LinkHTMLAttributes<HTMLLinkElement>, HTMLLinkElement>
> =
  import.meta.env.MODE === "test"
    ? []
    : [
        {
          rel: "preconnect",
          href: "https://fonts.googleapis.com",
        },
        {
          rel: "preconnect",
          href: "https://fonts.gstatic.com",
          crossOrigin: "anonymous" as const,
        },
        {
          rel: "stylesheet",
          href:
            "https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Noto+Sans:wght@400;600;700&family=Noto+Sans+SC:wght@400;700&display=swap",
        },
      ];

export const Route = createRootRoute({
  validateSearch: (search: Record<string, unknown>) => {
    const sid = normalizeSessionIdParam(search.sid);
    return sid ? { sid } : {};
  },
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Newbro Voice Writing Desk" },
      {
        name: "description",
        content:
          "A calm voice-first writing desk for the Synapse frontend shell.",
      },
    ],
    links: externalFontLinks,
  }),
  component: RootDocument,
  errorComponent: DefaultCatchBoundary,
  notFoundComponent: () => <NotFound />,
});

function RootDocument() {
  return (
    <>
      <HeadContent />
      <NewbroShellProvider>
        <Outlet />
      </NewbroShellProvider>
    </>
  );
}
