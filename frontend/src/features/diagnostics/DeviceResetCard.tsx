/**
 * Device-reset (factory reboot) card — the danger zone.
 *
 * Flow:
 *   1. Display a red-bordered explainer card with a "Reset to factory
 *      defaults…" button.
 *   2. On click, open the reusable DangerConfirmDialog with the switch IP as
 *      the confirmation value — pulled from `useIdentity()` so it always
 *      matches what the backend expects.
 *   3. On confirm, POST to /device-reset with `confirm_switch_host` set to
 *      the same IP the user typed.
 *   4. If the backend returns 403 (READ_ONLY) or 400 (host mismatch), show
 *      the error body inside the dialog.
 *
 * The backend takes a pre-write backup automatically (autobackup wrapper)
 * before issuing the reboot, so the operator can roll back once the switch
 * comes back up.
 */
import { useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { useIdentity } from "@/api/hooks/useIdentity";
import { useDeviceReset } from "@/api/hooks/useDiagnostics";

interface DeviceResetCardProps {
  /** Optional callback fired after a successful reset submission. */
  onReset?: () => void;
}

export function DeviceResetCard({ onReset }: DeviceResetCardProps) {
  const identity = useIdentity();
  const expectedIp = identity.data?.ip_address ?? "";
  const reset = useDeviceReset();
  const [open, setOpen] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const openDialog = () => {
    reset.reset();
    setLastResult(null);
    setOpen(true);
  };

  const handleConfirm = () => {
    if (!expectedIp) return;
    reset.mutate(
      { confirm_switch_host: expectedIp },
      {
        onSuccess: (data) => {
          setOpen(false);
          setLastResult(
            data.initiated
              ? "Reset initiated. The switch is rebooting; reconnect once it comes back up."
              : (data.message ?? "Reset request accepted."),
          );
          onReset?.();
        },
      },
    );
  };

  const errorMessage =
    reset.error instanceof Error ? reset.error.message : null;

  const ipReady = expectedIp.length > 0;

  const confirmationHint = (
    <>
      Expected:{" "}
      {ipReady ? (
        <span className="font-mono text-foreground">{expectedIp}</span>
      ) : identity.isLoading ? (
        <span className="italic">loading identity…</span>
      ) : (
        <span className="italic text-red-700 dark:text-red-300">
          unknown — identity not loaded
        </span>
      )}
    </>
  );

  const body = (
    <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
      <p className="font-semibold">Factory reset</p>
      <p className="mt-1">
        This reboots the switch and restores factory defaults — including
        removing the management IP and authorized-managers list. All switched
        traffic will drop for the duration of the reboot.
      </p>
      <p className="mt-2">
        A pre-write backup of the current running-config is taken automatically
        before the reset so you can roll back.
      </p>
    </div>
  );

  return (
    <>
      <section className="rounded-lg border border-red-300 dark:border-red-900 bg-red-50/50 dark:bg-red-950/40 p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wide text-red-700 dark:text-red-300">
              Danger zone
            </h4>
            <p className="mt-2 text-sm text-red-900 dark:text-red-300">
              Reset the switch to factory defaults. This reboots the device,
              drops traffic, and removes network configuration including the
              management IP.
            </p>
            {lastResult && (
              <p className="mt-2 text-sm italic text-foreground">
                {lastResult}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={openDialog}
            className="whitespace-nowrap rounded-md border border-red-600 bg-card px-3 py-1.5 text-sm font-semibold text-red-700 dark:text-red-300 shadow-sm hover:bg-red-100 dark:hover:bg-red-900/40"
          >
            Reset to factory defaults…
          </button>
        </div>
      </section>

      <DangerConfirmDialog
        open={open}
        title="Reset switch to factory defaults"
        body={body}
        confirmationValue={expectedIp}
        confirmationLabel="Type the switch IP to confirm"
        confirmationHint={confirmationHint}
        confirmationPlaceholder="e.g. 192.168.1.10"
        confirmButtonText="Reset switch"
        busyButtonText="Resetting…"
        onConfirm={handleConfirm}
        onCancel={() => setOpen(false)}
        busy={reset.isPending}
        error={
          errorMessage ? (
            <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
              <p className="font-semibold">Reset failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          ) : null
        }
      />
    </>
  );
}
