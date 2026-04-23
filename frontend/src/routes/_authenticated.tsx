import { createFileRoute, redirect } from "@tanstack/react-router";
import { AppShell } from "@/components/layout/AppShell";
import { apiGet, ApiError } from "@/api/client";
import type { components } from "@/api/schema";

type Whoami = components["schemas"]["WhoamiResponse"];

/**
 * Pathless layout route that enforces authentication. Every child route
 * (Identity, Status, Backups, etc.) inherits this guard.
 *
 * We call whoami through React Query's cache via `ensureQueryData` so the
 * first visit warms the cache and the TopBar's `useIdentity`/future hooks
 * don't each re-issue whoami. On a 401 we redirect to `/login`, preserving
 * the attempted path in `search.redirect` so post-login we can bounce back.
 */
export const Route = createFileRoute("/_authenticated")({
  beforeLoad: async ({ context, location }) => {
    try {
      await context.queryClient.ensureQueryData<Whoami>({
        queryKey: ["whoami"],
        queryFn: () => apiGet<Whoami>("/api/v1/auth/whoami"),
        staleTime: 60_000,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        throw redirect({
          to: "/login",
          search: { redirect: location.href },
        });
      }
      throw err;
    }
  },
  component: AppShell,
});
