import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import type { QueryClient } from "@tanstack/react-query";

/**
 * Router context shape. Passed via `createRouter({ context: {...} })` in
 * main.tsx so child routes (including the `_authenticated` guard) can run
 * React Query from within `beforeLoad`.
 */
export interface RouterContext {
  readonly queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
});

function RootComponent() {
  return <Outlet />;
}

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50">
      <div className="rounded-lg border border-neutral-200 bg-white p-6 text-center">
        <h1 className="text-xl font-semibold">Page not found</h1>
        <p className="mt-2 text-sm text-neutral-600">
          The page you requested does not exist.
        </p>
      </div>
    </div>
  );
}
