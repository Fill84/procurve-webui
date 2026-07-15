/**
 * Backups page (Task 2.13).
 *
 * Renders the list of stored backups and wires up the six UI actions the
 * backend exposes:
 *
 *   Header:  Take backup now  (POST /api/v1/backups)
 *   Row:     View diff        (GET  /api/v1/backups/{fn}/diff)
 *            Download         (GET  /api/v1/backups/{fn}/download)
 *            Restore          (POST /api/v1/backups/{fn}/restore, via dialog)
 *            Delete           (DELETE /api/v1/backups/{fn})
 *
 * Sort: the backend returns newest first; we preserve that order verbatim.
 *
 * Safety: deletion goes through `window.confirm`; restore goes through a
 * dedicated modal that requires typing the switch IP and surfaces the
 * READ_ONLY=true 403 with a helpful hint.
 *
 * Toast infra isn't set up yet for Phase 2, so we use an ephemeral inline
 * banner (`actionNotice`) for success feedback on take/download/delete.
 * Swapping to a real toast provider later is trivial.
 */
import { apiErrorMessage } from "@/api/client";
import { useMemo, useState } from "react";
import type { BackupMeta } from "@/api/hooks/useBackups";
import {
  useBackupsList,
  useCreateBackup,
  useDeleteBackup,
  useDownloadBackup,
  useLiveSha,
} from "@/api/hooks/useBackups";
import {
  RestoreDialog,
  DiffView,
} from "@/features/backups/RestoreDialog";
import { useDiffBackup } from "@/api/hooks/useBackups";
import { formatBytes } from "@/lib/format";

export function BackupsListPage() {
  const list = useBackupsList();
  const liveSha = useLiveSha();
  const createBackup = useCreateBackup();
  const deleteBackup = useDeleteBackup();
  const downloadBackup = useDownloadBackup();

  const [restoreTarget, setRestoreTarget] = useState<BackupMeta | null>(null);
  const [diffTarget, setDiffTarget] = useState<BackupMeta | null>(null);
  const [notice, setNotice] = useState<{
    tone: "ok" | "error";
    text: string;
  } | null>(null);

  const items = list.data ?? [];

  const liveShaShort = useMemo(() => {
    return liveSha.data?.sha256 ? liveSha.data.sha256.slice(0, 8) : null;
  }, [liveSha.data]);

  const handleTakeBackup = () => {
    setNotice(null);
    createBackup.mutate(undefined, {
      onSuccess: (meta) => {
        setNotice({
          tone: "ok",
          text: `Backup saved: ${meta.filename}`,
        });
      },
      onError: (err) => {
        setNotice({
          tone: "error",
          text: `Failed to take backup: ${
            apiErrorMessage(err)
          }`,
        });
      },
    });
  };

  const handleDownload = (filename: string) => {
    setNotice(null);
    downloadBackup.mutate(filename, {
      onError: (err) => {
        setNotice({
          tone: "error",
          text: `Download failed: ${
            apiErrorMessage(err)
          }`,
        });
      },
    });
  };

  const handleDelete = (filename: string) => {
    if (!window.confirm(`Delete backup "${filename}"? This cannot be undone.`)) {
      return;
    }
    setNotice(null);
    deleteBackup.mutate(filename, {
      onSuccess: () => {
        setNotice({ tone: "ok", text: `Deleted ${filename}.` });
      },
      onError: (err) => {
        setNotice({
          tone: "error",
          text: `Delete failed: ${
            apiErrorMessage(err)
          }`,
        });
      },
    });
  };

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Backups</h2>
          <p className="mt-0.5 text-xs text-neutral-500">
            Live config SHA256:{" "}
            {liveSha.isLoading ? (
              <span className="italic">loading…</span>
            ) : liveSha.isError ? (
              <span className="text-red-700">unavailable</span>
            ) : (
              <span className="font-mono">{liveShaShort ?? "—"}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => list.refetch()}
            disabled={list.isFetching}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            {list.isFetching ? "Refreshing…" : "Refresh"}
          </button>
          <button
            type="button"
            onClick={handleTakeBackup}
            disabled={createBackup.isPending}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:bg-blue-300"
          >
            {createBackup.isPending ? "Taking backup…" : "Take backup now"}
          </button>
        </div>
      </div>

      {/* Ephemeral notice (success/error for take/download/delete) */}
      {notice && (
        <div
          className={`mb-4 flex items-start justify-between gap-3 rounded-md border px-3 py-2 text-sm ${
            notice.tone === "ok"
              ? "border-green-300 bg-green-50 text-green-900"
              : "border-red-300 bg-red-50 text-red-900"
          }`}
        >
          <span>{notice.text}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-xs text-current opacity-70 hover:opacity-100"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Loading skeleton */}
      {list.isLoading && (
        <div className="grid gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-12 animate-pulse rounded border border-neutral-200 bg-neutral-100"
            />
          ))}
        </div>
      )}

      {/* Error banner + retry */}
      {list.isError && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
          <p className="font-medium">Failed to load backups</p>
          <p className="mt-1 text-sm opacity-80">
            {list.error instanceof Error
              ? list.error.message
              : String(list.error)}
          </p>
          <button
            type="button"
            onClick={() => list.refetch()}
            className="mt-3 rounded-md border border-red-400 bg-white px-3 py-1.5 text-sm font-medium text-red-900 hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {list.data && items.length === 0 && (
        <div className="rounded-lg border border-dashed border-neutral-300 bg-neutral-50 p-8 text-center">
          <p className="text-sm text-neutral-700">
            No backups yet — click{" "}
            <span className="font-semibold">Take backup now</span> to snapshot
            the current switch config.
          </p>
        </div>
      )}

      {/* Table */}
      {list.data && items.length > 0 && (
        <section className="overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-4 py-2 font-semibold">Timestamp</th>
                  <th className="px-4 py-2 font-semibold">Size</th>
                  <th className="px-4 py-2 font-semibold">SHA256</th>
                  <th className="px-4 py-2 font-semibold">Trigger</th>
                  <th className="px-4 py-2 font-semibold text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((b) => {
                  const isLive =
                    liveSha.data?.sha256 != null &&
                    liveSha.data.sha256 === b.sha256;
                  const busy =
                    (deleteBackup.isPending &&
                      deleteBackup.variables === b.filename) ||
                    (downloadBackup.isPending &&
                      downloadBackup.variables === b.filename);
                  return (
                    <tr
                      key={b.filename}
                      className="border-t border-neutral-100 align-middle"
                    >
                      <td className="px-4 py-2 font-mono text-xs text-neutral-700">
                        <div>{formatTimestamp(b.created_at)}</div>
                        <div className="text-[10px] text-neutral-400">
                          {b.filename}
                        </div>
                      </td>
                      <td className="px-4 py-2 text-neutral-700">
                        {formatBytes(b.size)}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-neutral-700">
                        <span title={b.sha256}>{b.sha256.slice(0, 8)}</span>
                        {isLive && (
                          <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-green-800">
                            live
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <TriggerBadge trigger={b.trigger} />
                      </td>
                      <td className="px-4 py-2 text-right">
                        <div className="inline-flex flex-wrap justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => setDiffTarget(b)}
                            className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
                          >
                            View diff
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDownload(b.filename)}
                            disabled={busy}
                            className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
                          >
                            Download
                          </button>
                          <button
                            type="button"
                            onClick={() => setRestoreTarget(b)}
                            className="rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
                          >
                            Restore…
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(b.filename)}
                            disabled={busy}
                            className="rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Restore modal */}
      <RestoreDialog
        backup={restoreTarget}
        onClose={() => setRestoreTarget(null)}
        onRestored={(filename) => {
          setNotice({
            tone: "ok",
            text: `Restore submitted for ${filename}.`,
          });
        }}
      />

      {/* Standalone diff viewer */}
      {diffTarget && (
        <DiffOnlyDialog
          backup={diffTarget}
          onClose={() => setDiffTarget(null)}
        />
      )}
    </div>
  );
}

/**
 * Read-only diff viewer used for the "View diff" row action. Shares the
 * DiffView component with RestoreDialog but omits the confirmation UI.
 */
function DiffOnlyDialog({
  backup,
  onClose,
}: {
  backup: BackupMeta;
  onClose: () => void;
}) {
  const diff = useDiffBackup(backup.filename, { enabled: true });
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="diff-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <button
        type="button"
        aria-label="Close dialog"
        onClick={onClose}
        className="absolute inset-0 bg-black/50"
      />
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-xl">
        <header className="flex items-start justify-between border-b border-neutral-200 px-5 py-3">
          <div>
            <h3
              id="diff-dialog-title"
              className="text-base font-semibold text-neutral-900"
            >
              Diff vs. live config
            </h3>
            <p className="mt-0.5 font-mono text-xs text-neutral-500">
              {backup.filename}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900"
          >
            Close
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {diff.isLoading && (
            <div className="h-40 animate-pulse rounded border border-neutral-200 bg-neutral-100" />
          )}
          {diff.isError && (
            <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              Failed to load diff:{" "}
              {diff.error instanceof Error
                ? diff.error.message
                : String(diff.error)}
            </div>
          )}
          {diff.data != null && <DiffView text={diff.data} />}
        </div>
      </div>
    </div>
  );
}

function TriggerBadge({ trigger }: { trigger: BackupMeta["trigger"] }) {
  // Each trigger gets a distinct colour so operators can scan the table
  // and tell manual snapshots apart from pre-write / scheduled ones.
  const style: Record<BackupMeta["trigger"], string> = {
    manual: "bg-blue-100 text-blue-900",
    "pre-write": "bg-amber-100 text-amber-900",
    scheduled: "bg-neutral-200 text-neutral-800",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style[trigger]}`}
    >
      {trigger}
    </span>
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return iso;
  // ISO-like but human-readable and sortable: "YYYY-MM-DD HH:MM:SSZ".
  return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
}
