import { useIdentity } from "@/api/hooks/useIdentity";
import { useLogout } from "@/api/hooks/useAuth";
import { useRouter } from "@tanstack/react-router";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Sticky top bar. Displays the switch's system_name from /api/v1/identity
 * (the field the user actually configured) with the model as a muted
 * suffix, and a logout button that clears the session cookie.
 */
export function TopBar() {
  const { data: identity } = useIdentity();
  const logout = useLogout();
  const router = useRouter();

  const handleLogout = () => {
    logout.mutate(undefined, {
      onSuccess: () => {
        void router.navigate({ to: "/login" });
      },
    });
  };

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-card px-6">
      <div className="flex items-baseline gap-3">
        <span className="text-lg font-semibold">
          {identity?.system_name ?? "ProCurve Switch"}
        </span>
        {identity?.product ? (
          <span className="text-sm text-muted-foreground">{identity.product}</span>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        <ThemeToggle />
        <button
          type="button"
          onClick={handleLogout}
          disabled={logout.isPending}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          {logout.isPending ? "Logging out..." : "Logout"}
        </button>
      </div>
    </header>
  );
}
