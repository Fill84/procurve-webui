/**
 * Restore confirmation dialog.
 *
 * Restoring a backup is the ONLY write path in Phase 2, so the UX is
 * deliberately friction-heavy:
 *
 *   1. Show a bright warning banner about management-IP lockout risk.
 *   2. Fetch and render the unified diff of the selected backup vs. live
 *      config so the admin can see exactly what changes on the switch.
 *   3. Require the admin to type the switch's management IP exactly before
 *      the "Restore" button becomes enabled. The IP comes from `useIdentity`
 *      so it is always sourced from the live switch, not a hard-coded value.
 *   4. If the backend returns 403 with `{error: "read_only"}` (the default
 *      posture in dev), show a helpful hint about flipping the env var
 *      instead of a generic "request failed" error.
 *
 * The modal is hand-rolled — shadcn's Dialog isn't installed in this repo
 * yet and the Phase 2 plan explicitly allows a plain overlay + centred panel
 * (no focus trap needed). If we add shadcn later we can swap the shell
 * without touching the rest of the page.
 */
import { useEffect, useRef, useState } from "react";
import { useIdentity } from "@/api/hooks/useIdentity";
import {
  useDiffBackup,
  useRestoreBackup,
  ReadOnlyRestoreError,
  type BackupMeta,
} from "@/api/hooks/useBackups";

interface RestoreDialogProps {
  /** The backup the user wants to restore. `null` closes the dialog. */
  backup: BackupMeta | null;
  onClose: () => void;
  onRestored: (filename: string) => void;
}

export function RestoreDialog({
  backup,
  onClose,
  onRestored,
}: RestoreDialogProps) {
  const open = backup != null;
  const identity = useIdentity();
  const expectedIp = identity.data?.ip_address ?? "";

  const [typedIp, setTypedIp] = useState("");
  const diff = useDiffBackup(backup?.filename ?? null, { enabled: open });
  const restore = useRestoreBackup();

  // Reset the IP confirmation and any prior mutation state whenever the
  // dialog opens for a new backup. We use the "changing prop -> derived
  // reset" pattern (https://react.dev/learn/you-might-not-need-an-effect
  // #resetting-all-state-when-a-prop-changes) instead of an effect, so we
  // don't trigger a cascading re-render after paint.
  const lastKeyRef = useRef<string | null>(null);
  const currentKey = open ? backup.filename : null;
  if (lastKeyRef.current !== currentKey) {
    lastKeyRef.current = currentKey;
    if (currentKey != null) {
      setTypedIp("");
      restore.reset();
    }
  }

  // Close on Escape — a minimal UX affordance that costs nothing.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !backup) return null;

  const ipReady = expectedIp.length > 0;
  const ipMatches = ipReady && typedIp.trim() === expectedIp;
  const canSubmit = ipMatches && !restore.isPending;

  const readOnlyError =
    restore.error instanceof ReadOnlyRestoreError ? restore.error : null;
  const otherError =
    restore.error && !readOnlyError
      ? restore.error instanceof Error
        ? restore.error.message
        : String(restore.error)
      : null;

  const handleSubmit = () => {
    restore.mutate(backup.filename, {
      onSuccess: () => {
        onRestored(backup.filename);
        onClose();
      },
    });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="restore-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close dialog"
        onClick={onClose}
        className="absolute inset-0 bg-black/50"
      />

      {/* Panel */}
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-xl">
        <header className="flex items-start justify-between border-b border-neutral-200 px-5 py-3">
          <div>
            <h3
              id="restore-dialog-title"
              className="text-base font-semibold text-neutral-900"
            >
              Restore backup
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
          {/* Warning */}
          <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-semibold">Connectivity risk</p>
            <p className="mt-1">
              Restoring this backup may change the management IP or
              authorized-managers list, potentially locking you out of the
              switch. Verify out-of-band access before proceeding.
            </p>
          </div>

          {/* Diff viewer */}
          <section className="mb-4">
            <header className="mb-2 flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Diff vs. live config
              </h4>
              {diff.isFetching && (
                <span className="text-xs text-neutral-500">Loading diff…</span>
              )}
            </header>
            {diff.isLoading && (
              <div className="h-40 animate-pulse rounded border border-neutral-200 bg-neutral-100" />
            )}
            {diff.isError && (
              <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">
                Failed to load diff:{" "}
                {diff.error instanceof Error
                  ? diff.error.message
                  : String(diff.error)}
              </div>
            )}
            {diff.data != null && <DiffView text={diff.data} />}
          </section>

          {/* Confirmation */}
          <section className="mb-2">
            <label className="block text-sm font-medium text-neutral-800">
              Type the switch IP to confirm
            </label>
            <p className="mt-0.5 text-xs text-neutral-500">
              Expected:{" "}
              {ipReady ? (
                <span className="font-mono text-neutral-700">{expectedIp}</span>
              ) : identity.isLoading ? (
                <span className="italic">loading identity…</span>
              ) : (
                <span className="italic text-red-700">
                  unknown — identity not loaded
                </span>
              )}
            </p>
            <input
              type="text"
              autoComplete="off"
              spellCheck={false}
              inputMode="numeric"
              value={typedIp}
              onChange={(e) => setTypedIp(e.target.value)}
              placeholder="e.g. 192.168.1.10"
              className="mt-2 w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </section>

          {/* Errors */}
          {readOnlyError && (
            <div className="mt-3 rounded-md border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-semibold">Restores are disabled</p>
              <p className="mt-1">{readOnlyError.detail}</p>
              <p className="mt-2 text-xs opacity-80">
                Set <code className="font-mono">READ_ONLY=false</code> in the
                backend environment and restart the service to enable restores.
              </p>
            </div>
          )}
          {otherError && (
            <div className="mt-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              <p className="font-semibold">Restore failed</p>
              <p className="mt-1 break-all">{otherError}</p>
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-neutral-200 bg-neutral-50 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={restore.isPending}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
          >
            {restore.isPending ? "Restoring…" : "Restore"}
          </button>
        </footer>
      </div>
    </div>
  );
}

/**
 * Render a unified diff with +/- line colouring. Lines starting with `+++`,
 * `---`, `@@`, or `\` are headers/markers and kept neutral. The container
 * enforces `white-space: pre` (no wrapping) so column alignment is preserved.
 */
export function DiffView({ text }: { text: string }) {
  if (text.length === 0) {
    return (
      <div className="rounded border border-neutral-200 bg-neutral-50 p-3 text-sm italic text-neutral-500">
        No differences — this backup matches the live config.
      </div>
    );
  }
  const lines = text.split("\n");
  return (
    <pre className="max-h-80 overflow-auto rounded border border-neutral-200 bg-neutral-50 p-3 text-xs leading-5">
      <code className="block whitespace-pre font-mono">
        {lines.map((line, i) => (
          <span key={i} className={diffLineClass(line)}>
            {line}
            {"\n"}
          </span>
        ))}
      </code>
    </pre>
  );
}

function diffLineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) {
    return "text-neutral-500";
  }
  if (line.startsWith("@@")) return "text-blue-700";
  if (line.startsWith("+")) return "text-green-700 bg-green-50";
  if (line.startsWith("-")) return "text-red-700 bg-red-50";
  return "text-neutral-800";
}
