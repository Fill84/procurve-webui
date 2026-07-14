/**
 * DangerConfirmDialog — generic "type a value to confirm" modal.
 *
 * Phase 3 introduces many write routes (VLAN, identity, passwords, ACLs,
 * reboots, etc.). Every one of them needs the same friction-heavy UX that
 * Phase 2's RestoreDialog pioneered: a modal with a warning body, an input
 * the user must type verbatim, and a confirm button that stays disabled
 * until the typed value matches.
 *
 * This component is the reusable shell. The caller supplies:
 *   - the visible body (warning banner + diff + anything else),
 *   - the string the user must type (typically the switch IP),
 *   - labels and button text,
 *   - the async `onConfirm` handler (plus busy/error state).
 *
 * The dialog itself manages only:
 *   - the local "typed" state (reset when `open` flips false -> true so the
 *     user never sees a pre-filled confirmation from a previous opening),
 *   - the submit-disabled gate,
 *   - Esc-to-close and backdrop-click-to-close (both suppressed while
 *     `busy` is true so an in-flight write can't be orphaned).
 *
 * No focus trap — matching the Phase 2 RestoreDialog's hand-rolled shell.
 * Swap to shadcn's Dialog later without touching callers.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";

export interface DangerConfirmDialogProps {
  /** Controls visibility. When this flips false -> true, the typed value resets. */
  open: boolean;
  /** Visible title (e.g. "Restore backup"). */
  title: string;
  /** Optional subtitle shown under the title (e.g. the backup filename). */
  subtitle?: ReactNode;
  /** Main dialog body. Rendered inside a scrollable region. */
  body: ReactNode;
  /** Exact string the user must type to enable the confirm button. */
  confirmationValue: string;
  /** Label shown above the confirmation input (e.g. "Type the switch IP to confirm"). */
  confirmationLabel: string;
  /** Optional placeholder for the confirmation input. */
  confirmationPlaceholder?: string;
  /** Optional hint line under the label (e.g. "Expected: 192.168.1.10"). */
  confirmationHint?: ReactNode;
  /** Primary button text when idle (e.g. "Restore"). */
  confirmButtonText: string;
  /** Optional primary button text while `busy` (falls back to "<confirmButtonText>…"). */
  busyButtonText?: string;
  /** Invoked when the user clicks the confirm button. May be async. */
  onConfirm: () => Promise<void> | void;
  /** Invoked when the user requests dismissal (close button / Esc / backdrop). */
  onCancel: () => void;
  /** When true, buttons + backdrop + Esc are locked while the mutation runs. */
  busy?: boolean;
  /** Optional error block rendered below the confirmation input. */
  error?: ReactNode;
}

export function DangerConfirmDialog({
  open,
  title,
  subtitle,
  body,
  confirmationValue,
  confirmationLabel,
  confirmationPlaceholder,
  confirmationHint,
  confirmButtonText,
  busyButtonText,
  onConfirm,
  onCancel,
  busy = false,
  error,
}: DangerConfirmDialogProps) {
  const [typed, setTyped] = useState("");

  // Reset typed-state whenever `open` flips false -> true (a fresh opening).
  // We use the "changing prop -> derived reset" pattern
  // (https://react.dev/learn/you-might-not-need-an-effect
  // #resetting-all-state-when-a-prop-changes) instead of an effect so we
  // don't trigger a cascading re-render after paint.
  const wasOpenRef = useRef(false);
  if (!wasOpenRef.current && open) {
    setTyped("");
  }
  wasOpenRef.current = open;

  // Close on Escape — a minimal UX affordance. Suppressed while `busy`.
  useEffect(() => {
    if (!open || busy) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  const matches = typed.trim() === confirmationValue && confirmationValue.length > 0;
  const canSubmit = matches && !busy;

  const handleBackdropClick = () => {
    if (!busy) onCancel();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="danger-confirm-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close dialog"
        onClick={handleBackdropClick}
        disabled={busy}
        className="absolute inset-0 bg-black/50 disabled:cursor-not-allowed"
      />

      {/* Panel */}
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-border bg-card text-card-foreground shadow-xl">
        <header className="flex items-start justify-between border-b border-border px-5 py-3">
          <div>
            <h3
              id="danger-confirm-dialog-title"
              className="text-base font-semibold text-foreground"
            >
              {title}
            </h3>
            {subtitle != null && (
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            Close
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {body}

          {/* Confirmation */}
          <section className="mt-4">
            <label className="block text-sm font-medium text-foreground">
              {confirmationLabel}
            </label>
            {confirmationHint != null && (
              <p className="mt-0.5 text-xs text-muted-foreground">{confirmationHint}</p>
            )}
            <input
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={confirmationPlaceholder}
              disabled={busy}
              className="mt-2 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-muted disabled:text-muted-foreground"
            />
          </section>

          {error != null && <div className="mt-3">{error}</div>}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border bg-muted px-5 py-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              void onConfirm();
            }}
            disabled={!canSubmit}
            className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
          >
            {busy ? (busyButtonText ?? `${confirmButtonText}…`) : confirmButtonText}
          </button>
        </footer>
      </div>
    </div>
  );
}
