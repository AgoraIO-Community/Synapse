/// <reference types="vite/client" />
import { HeadContent, Outlet, createRootRoute } from "@tanstack/react-router";
import type { DetailedHTMLProps, LinkHTMLAttributes } from "react";
import { DefaultCatchBoundary } from "../components/DefaultCatchBoundary";
import { NotFound } from "../components/NotFound";
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
            "https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Sans+SC:wght@400;700&display=swap",
        },
      ];

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Newbro Voice Command Center" },
      {
        name: "description",
        content:
          "Sample-style Newbro voice command center shell for the Synapse frontend.",
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
