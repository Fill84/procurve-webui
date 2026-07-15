/**
 * Typed fetch helpers for the ProCurve WebUI backend.
 *
 * Every helper sets `credentials: "include"` so the browser sends the signed
 * session cookie (issued by the backend on `/api/v1/auth/login`) with each
 * request. Without this the backend's auth middleware rejects the request as
 * unauthenticated, because the cookie is same-site but still requires the
 * explicit credentials mode for programmatic fetch.
 *
 * The `paths` import from the generated schema is re-exported for callers
 * that want to narrow responses via `paths["/api/v1/identity"]["get"]...`.
 */
import type { paths } from "./schema";

export type { paths };

/** Thrown on any non-2xx response. `body` holds the raw response text. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/**
 * Extract the human-readable message from any error this app produces.
 *
 * The backend guarantees a flat `{"error": <slug>, "detail": <string>}`
 * envelope on every error response (see backend/app/errors.py), so for an
 * `ApiError` we surface `detail` instead of the raw
 * `API 500: {"error":...}` JSON string cards used to render at users.
 * Falls back gracefully for non-JSON bodies and plain Errors.
 *
 * Returns `null` for `null`/`undefined` so call sites can do
 * `apiErrorMessage(mutation.error)` without their own null guard.
 */
export function apiErrorMessage(err: unknown): string | null {
  if (err == null) return null;
  if (err instanceof ApiError) {
    try {
      const body = JSON.parse(err.body) as Record<string, unknown>;
      if (typeof body.detail === "string" && body.detail) return body.detail;
      if (typeof body.error === "string" && body.error) return body.error;
    } catch {
      // Non-JSON body — fall through to the raw text.
    }
    return err.body || `Request failed (HTTP ${err.status})`;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

/** GET a JSON endpoint. */
export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(path, { credentials: "include" });
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return (await r.json()) as T;
}

/** POST JSON (or nothing) and return JSON. */
export async function apiPost<T, B = unknown>(
  path: string,
  body?: B,
): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return (await r.json()) as T;
}

/** PUT JSON and return JSON. */
export async function apiPut<T, B = unknown>(
  path: string,
  body: B,
): Promise<T> {
  const r = await fetch(path, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return (await r.json()) as T;
}

/** DELETE a resource and return JSON. */
export async function apiDelete<T>(path: string): Promise<T> {
  const r = await fetch(path, { method: "DELETE", credentials: "include" });
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return (await r.json()) as T;
}
