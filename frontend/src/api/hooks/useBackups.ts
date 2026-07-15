/**
 * React Query hooks for the Backups feature (Task 2.13).
 *
 * Backend endpoints (already implemented in Task 2.4):
 *   GET    /api/v1/backups                       -> BackupMeta[]
 *   POST   /api/v1/backups                       -> BackupMeta (201)
 *   GET    /api/v1/backups/live-sha              -> { sha256 }
 *   GET    /api/v1/backups/{filename}/download   -> octet-stream
 *   GET    /api/v1/backups/{filename}/diff       -> text/plain unified diff
 *   POST   /api/v1/backups/{filename}/restore    -> 200 | 403 when READ_ONLY=true
 *   DELETE /api/v1/backups/{filename}            -> 204
 *
 * Notes:
 *   - The list endpoint returns a bare array (not `{items}`). The generated
 *     schema confirms `BackupMeta[]`.
 *   - The diff endpoint returns `text/plain`, so we cannot use the generic
 *     `apiGet<T>` (which parses JSON). `fetchDiffText` handles that case.
 *   - Restore returns 200 JSON on success and 403 JSON on READ_ONLY; we keep
 *     the 403 body accessible to the UI for the helpful "flip the env var"
 *     message instead of the generic ApiError string.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { apiGet, apiPost, ApiError } from "@/api/client";
import type { components } from "@/api/schema";

export type BackupMeta = components["schemas"]["BackupMeta"];
export type CreateBackupRequest = components["schemas"]["CreateBackupRequest"];
export type LiveShaResponse = components["schemas"]["LiveShaResponse"];

const BACKUPS_KEY = ["backups"] as const;

/** List all stored backups. Backend returns newest first; we preserve that. */
export function useBackupsList() {
  return useQuery<BackupMeta[]>({
    queryKey: BACKUPS_KEY,
    queryFn: () => apiGet<BackupMeta[]>("/api/v1/backups"),
  });
}

/** SHA256 of the live config. Used to tell when a backup matches live. */
export function useLiveSha() {
  return useQuery<LiveShaResponse>({
    queryKey: ["backups", "live-sha"],
    queryFn: () => apiGet<LiveShaResponse>("/api/v1/backups/live-sha"),
  });
}

/** Take a new backup (defaults to manual trigger). */
export function useCreateBackup() {
  const qc = useQueryClient();
  return useMutation<BackupMeta, ApiError, CreateBackupRequest | undefined>({
    mutationFn: (body) =>
      apiPost<BackupMeta, CreateBackupRequest>(
        "/api/v1/backups",
        body ?? { trigger: "manual" },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: BACKUPS_KEY });
    },
  });
}

/**
 * Trigger a browser download for a stored backup.
 *
 * We fetch as a blob (so the cookie gets sent and errors are catchable)
 * and then synthesise an `<a download>` click to save it with the correct
 * filename. The object URL is revoked after the click.
 */
export async function downloadBackup(filename: string): Promise<void> {
  const r = await fetch(
    `/api/v1/backups/${encodeURIComponent(filename)}/download`,
    { credentials: "include" },
  );
  if (!r.ok) throw new ApiError(r.status, await r.text());
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Hook wrapper around `downloadBackup` so components can use a mutation-like
 * API (trigger + in-flight state) without wiring up their own async state.
 */
export function useDownloadBackup() {
  return useMutation<void, ApiError, string>({
    mutationFn: (filename) => downloadBackup(filename),
  });
}

/** Fetch the unified diff text. Diff endpoint returns `text/plain`. */
async function fetchDiffText(filename: string): Promise<string> {
  const r = await fetch(
    `/api/v1/backups/${encodeURIComponent(filename)}/diff`,
    { credentials: "include" },
  );
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return await r.text();
}

/**
 * Lazy diff fetch. Callers pass `enabled: false` and then toggle to true
 * when a dialog opens so we don't hammer the switch for backups the user
 * isn't actively inspecting.
 */
export function useDiffBackup(
  filename: string | null,
  options?: Omit<UseQueryOptions<string>, "queryKey" | "queryFn">,
) {
  return useQuery<string>({
    queryKey: ["backups", "diff", filename],
    queryFn: () => fetchDiffText(filename as string),
    enabled: filename != null && (options?.enabled ?? true),
    ...options,
  });
}

/**
 * Restore error surfaced to the UI. Preserves the 403 READ_ONLY body so the
 * dialog can render a user-friendly "flip the env var" hint. All other non-2xx
 * responses raise a generic `ApiError` as usual.
 */
export class ReadOnlyRestoreError extends Error {
  readonly detail: string;

  constructor(detail: string) {
    super(detail);
    this.name = "ReadOnlyRestoreError";
    this.detail = detail;
  }
}

interface RestoreSuccess {
  status: string;
  filename: string;
  sha256: string;
  /** Filename of the pre-restore snapshot of the live config (rollback point). */
  pre_restore_backup: string | null;
}

export interface RestoreVars {
  filename: string;
  /** Must equal the backend's SWITCH_HOST — same contract as device-reset. */
  confirmSwitchHost: string;
}

async function postRestore({
  filename,
  confirmSwitchHost,
}: RestoreVars): Promise<RestoreSuccess> {
  const r = await fetch(
    `/api/v1/backups/${encodeURIComponent(filename)}/restore`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm_switch_host: confirmSwitchHost }),
    },
  );
  if (r.status === 403) {
    // Backend shape: { error: "read_only", detail: "<human message>" }
    let detail = "Restore is disabled (READ_ONLY=true).";
    try {
      const body = (await r.json()) as { error?: string; detail?: string };
      if (body?.error === "read_only" && body.detail) detail = body.detail;
    } catch {
      // Body wasn't JSON; fall back to default.
    }
    throw new ReadOnlyRestoreError(detail);
  }
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return (await r.json()) as RestoreSuccess;
}

export function useRestoreBackup() {
  const qc = useQueryClient();
  return useMutation<
    RestoreSuccess,
    ApiError | ReadOnlyRestoreError,
    RestoreVars
  >({
    mutationFn: postRestore,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: BACKUPS_KEY });
    },
  });
}

/** Delete a stored backup. Returns void; backend returns 204. */
export function useDeleteBackup() {
  const qc = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: async (filename) => {
      // 204 No Content -> apiDelete<> would choke on empty body; use raw fetch.
      const r = await fetch(
        `/api/v1/backups/${encodeURIComponent(filename)}`,
        { method: "DELETE", credentials: "include" },
      );
      if (!r.ok) throw new ApiError(r.status, await r.text());
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: BACKUPS_KEY });
    },
  });
}

