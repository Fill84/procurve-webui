/**
 * WebAccessCard — toggle HTTPS on/off + change the SSL port.
 *
 * LOCKOUT RISK: enabling HTTPS-only without a valid certificate installed
 * kicks the browser straight into a trust error that many users can't click
 * through, and the firmware won't fall back to HTTP. So:
 *   1. Surface a bright warning banner.
 *   2. Gate [Save] behind the shared DangerConfirmDialog — the user must
 *      type the current switch IP to confirm.
 *
 * We don't render a password form here. Per
 * ``memory/feedback_switch_write_safety.md`` the device-password write has no
 * HTTP surface at all.
 */
import { useEffect, useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { useIdentity } from "@/api/hooks/useIdentity";
import {
  useSetWebAccess,
  useSslState,
  type SetSSLRequest,
} from "@/api/hooks/useSecurity";

export function WebAccessCard() {
  const identity = useIdentity();
  const sslQuery = useSslState();
  const setWebAccess = useSetWebAccess();

  const [enabled, setEnabled] = useState(false);
  const [port, setPort] = useState(443);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  // Seed local form state from the fetched state the first time it arrives.
  useEffect(() => {
    if (sslQuery.data) {
      setEnabled(sslQuery.data.ssl_enabled);
      setPort(sslQuery.data.ssl_port);
    }
  }, [sslQuery.data]);

  const expectedIp = identity.data?.ip_address ?? "";

  const handleSave = () => {
    setLastResult(null);
    setWebAccess.reset();
    setDialogOpen(true);
  };

  const handleConfirm = () => {
    if (!expectedIp) return;
    const request: SetSSLRequest = {
      enabled: enabled ? 2 : 1,
      port: port,
      cert_mode: 2,
    };
    setWebAccess.mutate(
      { request, confirm_switch_host: expectedIp },
      {
        onSuccess: (data) => {
          setDialogOpen(false);
          setLastResult(
            data.applied
              ? "SSL settings applied. The management session may drop."
              : (data.message ?? "Request accepted."),
          );
        },
      },
    );
  };

  const errorMessage =
    setWebAccess.error instanceof Error ? setWebAccess.error.message : null;

  const body = (
    <div className="space-y-3">
      <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
        <p className="font-semibold">Lockout risk</p>
        <p className="mt-1">
          Enabling HTTPS-only without a valid certificate installed will lock
          you out of the web UI. The browser will refuse to present the
          self-signed certificate without an override, and the firmware does
          not fall back to HTTP while HTTPS is on. Keep an SSH session open
          before toggling this.
        </p>
      </div>
      <div className="rounded border border-neutral-200 bg-neutral-50 p-3 text-sm">
        <p>
          <span className="font-semibold">Proposed:</span>{" "}
          HTTPS {enabled ? "ON" : "OFF"} on port{" "}
          <span className="font-mono">{port}</span>
        </p>
      </div>
    </div>
  );

  const confirmationHint = (
    <>
      Expected:{" "}
      {expectedIp ? (
        <span className="font-mono text-neutral-700">{expectedIp}</span>
      ) : (
        <span className="italic">loading identity…</span>
      )}
    </>
  );

  return (
    <>
      <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
            Web access (HTTP / HTTPS)
          </h4>
          {sslQuery.isLoading && (
            <span className="text-xs text-neutral-500">Loading…</span>
          )}
        </div>

        {sslQuery.error instanceof Error && (
          <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
            Failed to fetch SSL state: {sslQuery.error.message}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-[auto,8rem,auto] md:items-end">
          <div>
            <label className="block text-xs font-medium text-neutral-700">
              Mode
            </label>
            <div className="mt-1 flex items-center gap-4 text-sm">
              <label className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name="web-access-mode"
                  checked={!enabled}
                  onChange={() => setEnabled(false)}
                />
                HTTP
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name="web-access-mode"
                  checked={enabled}
                  onChange={() => setEnabled(true)}
                />
                HTTPS
              </label>
            </div>
          </div>

          <div>
            <label
              htmlFor="ssl-port"
              className="block text-xs font-medium text-neutral-700"
            >
              SSL port
            </label>
            <input
              id="ssl-port"
              type="number"
              min={1}
              max={65535}
              value={port}
              onChange={(e) => setPort(Number(e.target.value) || 443)}
              disabled={!enabled}
              className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-neutral-50"
            />
          </div>

          <button
            type="button"
            onClick={handleSave}
            disabled={!expectedIp || setWebAccess.isPending}
            className="justify-self-start rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:bg-red-300"
          >
            Save (dangerous)…
          </button>
        </div>

        {lastResult && (
          <p className="mt-3 text-sm italic text-neutral-700">{lastResult}</p>
        )}
      </section>

      <DangerConfirmDialog
        open={dialogOpen}
        title="Apply web-access change"
        body={body}
        confirmationValue={expectedIp}
        confirmationLabel="Type the switch IP to confirm"
        confirmationHint={confirmationHint}
        confirmationPlaceholder="e.g. 192.168.1.10"
        confirmButtonText="Apply SSL change"
        busyButtonText="Applying…"
        onConfirm={handleConfirm}
        onCancel={() => setDialogOpen(false)}
        busy={setWebAccess.isPending}
        error={
          errorMessage ? (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              <p className="font-semibold">Apply failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          ) : null
        }
      />
    </>
  );
}
