import { createFileRoute } from "@tanstack/react-router";
import { LoginScreen } from "@/features/auth/LoginScreen";

/**
 * Login route lives OUTSIDE the `_authenticated` prefix so the auth guard
 * never runs here — otherwise an unauthenticated user would be caught in
 * an infinite redirect loop. The `redirect` search param is optional and
 * reserved for a future "return to original page after login" flow.
 */
type LoginSearch = {
  readonly redirect?: string;
};

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: typeof search.redirect === "string" ? search.redirect : undefined,
  }),
  component: LoginScreen,
});
