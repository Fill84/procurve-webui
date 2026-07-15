import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "./api/client";
import { routeTree } from "./routeTree.gen";
import { ThemeProvider } from "./lib/theme";
import "./styles/globals.css";

const queryClient = new QueryClient({
  // Session-expiry handling: when any query starts failing with 401 (the
  // dashboard polls hit this within seconds of expiry), bounce to /login
  // with the current path as the return target instead of leaving the page
  // silently erroring every poll cycle. A hard navigation deliberately
  // resets all in-memory state for the fresh session.
  queryCache: new QueryCache({
    onError: (error) => {
      if (
        error instanceof ApiError &&
        error.status === 401 &&
        window.location.pathname !== "/login"
      ) {
        const back = encodeURIComponent(
          window.location.pathname + window.location.search,
        );
        window.location.assign(`/login?redirect=${back}`);
      }
    },
  }),
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      // Switch read-safety: every query here scrapes a CGI on a fragile
      // embedded switch, so remounting a tab must NOT refire ~10 requests.
      // 30 s staleness means tab-bouncing costs zero switch traffic; the
      // dashboards that need fresher data poll via explicit refetchInterval,
      // which is unaffected by staleTime.
      staleTime: 30_000,
    },
  },
});

// `context` is typed by the root route via `createRootRouteWithContext`.
// It is injected into every route's loader/beforeLoad so the auth guard
// can reach React Query without importing main.tsx (which would create a
// cycle).
const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element #root not found in index.html");
}

createRoot(rootEl).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
