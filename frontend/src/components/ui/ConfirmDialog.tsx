/**
 * ConfirmDialog — lightweight Yes/No modal for non-destructive confirmations.
 *
 * Counterpart to {@link ./DangerConfirmDialog} which is reserved for
 * lockout-risky writes (it forces the operator to type the switch IP).
 * Use this one for routine "are you sure?" prompts where a typed
 * confirmation would be excessive friction — fault-log delete, etc.
 *
 * Same shell shape as DangerConfirmDialog so the two dialogs feel
 * consistent: backdrop click + Esc dismiss (suppressed while busy),
 * footer with Cancel + primary action, optional inline error.
 */
import { useEffect, type ReactNode } from "react";

export interface ConfirmDialogProps {
  /** Controls visibility. */
  open: boolean;
  /** Visible title (e.g. "Delete events"). */
  title: string;
  /** Optional subtitle line under the title. */
  subtitle?: ReactNode;
  /** Main dialog body. */
  body: ReactNode;
  /** Primary button text when idle. */
  confirmLabel: string;
  /** Optional primary button text while `busy` (falls back to "<confirmLabel>…"). */
  busyLabel?: string;
  /** Cancel button text. Defaults to "Cancel". */
  cancelLabel?: string;
  /** Visual tone of the primary button. */
  tone?: "default" | "danger";
  /** Disables buttons / Esc / backdrop click while a mutation is running. */
  busy?: boolean;
  /** Optional error block rendered below the body. */
  error?: ReactNode;
  /** Invoked when the user clicks the primary action. May be async. */
  onConfirm: () => Promise<void> | void;
  /** Invoked when the user requests dismissal (Cancel / Esc / backdrop). */
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  subtitle,
  body,
  confirmLabel,
  busyLabel,
  cancelLabel = "Cancel",
  tone = "default",
  busy = false,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open || busy) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  const handleBackdropClick = () => {
    if (!busy) onCancel();
  };

  const primaryClasses =
    tone === "danger"
      ? "rounded-md bg-red-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
      : "rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-neutral-800 disabled:cursor-not-allowed disabled:bg-neutral-400";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <button
        type="button"
        aria-label="Close dialog"
        onClick={handleBackdropClick}
        disabled={busy}
        className="absolute inset-0 bg-black/50 disabled:cursor-not-allowed"
      />

      <div className="relative z-10 flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-xl">
        <header className="flex items-start justify-between border-b border-neutral-200 px-5 py-3">
          <div>
            <h3
              id="confirm-dialog-title"
              className="text-base font-semibold text-neutral-900"
            >
              {title}
            </h3>
            {subtitle != null && (
              <p className="mt-0.5 text-xs text-neutral-500">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md px-2 py-1 text-sm text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 disabled:opacity-50"
          >
            Close
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4 text-sm text-neutral-800">
          {body}
          {error != null && <div className="mt-3">{error}</div>}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-neutral-200 bg-neutral-50 px-5 py-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={() => {
              void onConfirm();
            }}
            disabled={busy}
            className={primaryClasses}
          >
            {busy ? (busyLabel ?? `${confirmLabel}…`) : confirmLabel}
          </button>
        </footer>
      </div>
    </div>
  );
}
