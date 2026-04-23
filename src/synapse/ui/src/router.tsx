import { createRoute, createRouter, useNavigate } from "@tanstack/react-router";
import type { PageId } from "./components/newbro";
import { DefaultCatchBoundary } from "./components/DefaultCatchBoundary";
import { NotFound } from "./components/NotFound";
import {
  BrosShellPage,
  HomeShellPage,
  NodesShellPage,
  SettingsShellPage,
} from "./NewbroShell";
import { Route as rootRoute } from "./routes/__root";

function pageToPath(page: PageId): "/" | "/bros" | "/nodes" | "/settings" {
  if (page === "Bros") return "/bros";
  if (page === "Nodes") return "/nodes";
  if (page === "Settings") return "/settings";
  return "/";
}

function usePageNavigate() {
  const navigate = useNavigate();
  return (page: PageId) => {
    void navigate({
      href: `${pageToPath(page)}${window.location.search}`,
    });
  };
}

function HomeRouteComponent() {
  return <HomeShellPage onNavigate={usePageNavigate()} />;
}

function BrosRouteComponent() {
  return <BrosShellPage onNavigate={usePageNavigate()} />;
}

function NodesRouteComponent() {
  return <NodesShellPage onNavigate={usePageNavigate()} />;
}

function SettingsRouteComponent() {
  return <SettingsShellPage onNavigate={usePageNavigate()} />;
}

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomeRouteComponent,
});

const brosRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/bros",
  component: BrosRouteComponent,
});

const nodesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/nodes",
  component: NodesRouteComponent,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsRouteComponent,
});

const routeTree = rootRoute.addChildren([
  homeRoute,
  brosRoute,
  nodesRoute,
  settingsRoute,
]);

export function getRouter() {
  return createRouter({
    routeTree,
    defaultPreload: "intent",
    defaultErrorComponent: DefaultCatchBoundary,
    defaultNotFoundComponent: () => <NotFound />,
    scrollRestoration: false,
  });
}
