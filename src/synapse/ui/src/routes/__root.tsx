/// <reference types="vite/client" />
import { HeadContent, Outlet, createRootRoute } from "@tanstack/react-router";
import { DefaultCatchBoundary } from "../components/DefaultCatchBoundary";
import { NotFound } from "../components/NotFound";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "NewBro Workbench" },
      {
        name: "description",
        content:
          "Chat-first workbench for the NewBro communication-brain and execution-brain runtime.",
      },
    ],
    links: [
      {
        rel: "preconnect",
        href: "https://fonts.googleapis.com",
      },
      {
        rel: "preconnect",
        href: "https://fonts.gstatic.com",
        crossOrigin: "anonymous",
      },
      {
        rel: "stylesheet",
        href:
          "https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Sans+SC:wght@400;700&display=swap",
      },
    ],
  }),
  component: RootDocument,
  errorComponent: DefaultCatchBoundary,
  notFoundComponent: () => <NotFound />,
});

function RootDocument() {
  return (
    <>
      <HeadContent />
      <Outlet />
    </>
  );
}
