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
 * The modal shell + the "type value to confirm" input live in the reusable
 * DangerConfirmDialog component (Phase 3 extracts it so every new write
 * route can share it). This module is now responsible only for the
 * restore-specific body — warning banner, diff viewer, and error rendering.
 */
import { useRef } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
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

  const diff = useDiffBackup(backup?.filename ?? null, { enabled: open });
  const restore = useRestoreBackup();

  // Reset any prior mutation state whenever the dialog opens for a new
  // backup. We use the "changing prop -> derived reset" pattern
  // (https://react.dev/learn/you-might-not-need-an-effect
  // #resetting-all-state-when-a-prop-changes) instead of an effect, so we
  // don't trigger a cascading re-render after paint. DangerConfirmDialog
  // owns the typed-input reset on its own.
  const lastKeyRef = useRef<string | null>(null);
  const currentKey = open ? backup.filename : null;
  if (lastKeyRef.current !== currentKey) {
    lastKeyRef.current = currentKey;
    if (currentKey != null) {
      restore.reset();
    }
  }

  if (!open || !backup) return null;

  const readOnlyError =
    restore.error instanceof ReadOnlyRestoreError ? restore.error : null;
  const otherError =
    restore.error && !readOnlyError
      ? restore.error instanceof Error
        ? restore.error.message
        : String(restore.error)
      : null;

  const handleConfirm = () => {
    // Same contract as device-reset: the backend re-verifies this value
    // against SWITCH_HOST server-side (require_host_confirmation), and takes
    // a pre-restore snapshot of the live config before uploading.
    if (!expectedIp) return;
    restore.mutate(
      { filename: backup.filename, confirmSwitchHost: expectedIp },
      {
        onSuccess: () => {
          onRestored(backup.filename);
          onClose();
        },
      },
    );
  };

  const body = (
    <>
      {/* Warning */}
      <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-semibold">Connectivity risk</p>
        <p className="mt-1">
          Restoring this backup may change the management IP or
          authorized-managers list, potentially locking you out of the switch.
          Verify out-of-band access before proceeding.
        </p>
      </div>

      {/* Diff viewer */}
      <section className="mb-2">
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
    </>
  );

  const ipReady = expectedIp.length > 0;
  const confirmationHint = (
    <>
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
    </>
  );

  const errorNode =
    readOnlyError != null ? (
      <div className="rounded-md border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-semibold">Restores are disabled</p>
        <p className="mt-1">{readOnlyError.detail}</p>
        <p className="mt-2 text-xs opacity-80">
          Set <code className="font-mono">READ_ONLY=false</code> in the backend
          environment and restart the service to enable restores.
        </p>
      </div>
    ) : otherError != null ? (
      <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
        <p className="font-semibold">Restore failed</p>
        <p className="mt-1 break-all">{otherError}</p>
      </div>
    ) : null;

  return (
    <DangerConfirmDialog
      open={open}
      title="Restore backup"
      subtitle={backup.filename}
      body={body}
      // When identity hasn't loaded yet, `expectedIp` is "" — DangerConfirmDialog
      // treats an empty confirmationValue as "can never match", so the submit
      // button stays disabled until we know which IP to compare against.
      confirmationValue={expectedIp}
      confirmationLabel="Type the switch IP to confirm"
      confirmationHint={confirmationHint}
      confirmationPlaceholder="e.g. 192.168.1.10"
      confirmButtonText="Restore"
      busyButtonText="Restoring…"
      onConfirm={handleConfirm}
      onCancel={onClose}
      busy={restore.isPending}
      error={errorNode}
    />
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
