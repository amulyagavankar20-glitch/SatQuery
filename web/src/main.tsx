import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Outlet, RouterProvider, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";

import { GlobalOverlays } from "@/components/GlobalOverlays";
import { ConsolePage } from "@/pages/ConsolePage";
import { AboutPage } from "@/pages/AboutPage";
import { ExplorePage } from "@/pages/ExplorePage";
import { ConsoleProvider } from "@/state/console";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function RootLayout() {
  return (
    <ConsoleProvider>
      <Outlet />
      <GlobalOverlays />
    </ConsoleProvider>
  );
}

const rootRoute = createRootRoute({ component: RootLayout });
const consoleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ConsolePage,
});
const aboutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/about",
  component: AboutPage,
});
const exploreRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/explore",
  component: ExplorePage,
});

const routeTree = rootRoute.addChildren([consoleRoute, aboutRoute, exploreRoute]);
const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
