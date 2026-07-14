import { useState, type FormEvent } from "react";
import { useRouter } from "@tanstack/react-router";
import { useLogin } from "@/api/hooks/useAuth";

/**
 * Standalone login page. On successful submit the whoami query is
 * invalidated (in `useLogin`), then we navigate to `/`, which triggers
 * the `_authenticated` layout's beforeLoad guard to re-run and let the
 * user through.
 */
export function LoginScreen() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const router = useRouter();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    login.mutate(
      { username, password },
      {
        onSuccess: () => {
          void router.navigate({ to: "/" });
        },
      },
    );
  };

  const errorMessage = login.isError
    ? login.error.status === 401
      ? "Invalid username or password."
      : `Login failed: ${login.error.body || login.error.message}`
    : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-border bg-card text-card-foreground p-6 shadow-sm"
      >
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">ProCurve WebUI</h1>
          <p className="text-sm text-muted-foreground">
            Sign in with your switch credentials.
          </p>
        </div>

        {errorMessage ? (
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
          >
            {errorMessage}
          </div>
        ) : null}

        <div className="space-y-1.5">
          <label htmlFor="username" className="block text-sm font-medium">
            Username
          </label>
          <input
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={login.isPending}
            className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:border-ring focus:ring-1 focus:ring-ring disabled:opacity-50"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={login.isPending}
            className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:border-ring focus:ring-1 focus:ring-ring disabled:opacity-50"
          />
        </div>

        <button
          type="submit"
          disabled={login.isPending}
          className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {login.isPending ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
