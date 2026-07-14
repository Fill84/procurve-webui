/**
 * IpConfigCard — view / edit the management-interface IP configuration.
 *
 * LOCKOUT RISK: changing VLAN / DHCP mode / gateway on the management
 * interface can sever the operator's session to the switch. We apply the
 * same friction pattern as the Security tab's WebAccessCard:
 *
 *   1. Read-only display by default.
 *   2. [Edit] reveals the form.
 *   3. [Save] opens the shared DangerConfirmDialog — the operator must
 *      type the current switch IP to confirm.
 *   4. Bright warning banner in the dialog body.
 *
 * The switch IP used as the confirmation value comes from ``useIdentity``
 * (which returns the identity-page scrape). This mirrors how the
 * Security tab resolves ``confirm_switch_host``.
 */
import { useEffect, useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { useIdentity } from "@/api/hooks/useIdentity";
import {
  useIpConfig,
  useSetIpConfig,
  type IpMode,
  type SetIpConfigRequest,
} from "@/api/hooks/useConfiguration";

// Mirror backend IpMode enum values.
const MODE_DISABLED: IpMode = 1;
const MODE_MANUAL: IpMode = 2;
const MODE_DHCP: IpMode = 3;

function modeLabel(mode: IpMode): string {
  switch (mode) {
    case MODE_DISABLED:
      return "Disabled";
    case MODE_MANUAL:
      return "Manual (static)";
    case MODE_DHCP:
      return "DHCP / Bootp";
    default:
      return String(mode);
  }
}

export function IpConfigCard() {
  const identity = useIdentity();
  const query = useIpConfig();
  const mutation = useSetIpConfig();

  const [editing, setEditing] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  // Local form state — seeded from the fetched page.
  const [vlanId, setVlanId] = useState(1);
  const [mode, setMode] = useState<IpMode>(MODE_MANUAL);
  const [gateway, setGateway] = useState("");

  useEffect(() => {
    if (query.data) {
      setVlanId(query.data.vlan_id);
      setMode(query.data.mode);
      setGateway(query.data.gateway);
    }
  }, [query.data]);

  const expectedIp = identity.data?.ip_address ?? "";

  const handleEdit = () => {
    setEditing(true);
    setLastResult(null);
    mutation.reset();
  };

  const handleCancel = () => {
    if (query.data) {
      setVlanId(query.data.vlan_id);
      setMode(query.data.mode);
      setGateway(query.data.gateway);
    }
    setEditing(false);
    mutation.reset();
  };

  const handleSave = () => {
    setLastResult(null);
    mutation.reset();
    setDialogOpen(true);
  };

  const handleConfirm = () => {
    if (!expectedIp) return;
    const request: SetIpConfigRequest = {
      gateway: gateway.trim(),
      vlan_id: vlanId,
      mode,
    };
    mutation.mutate(
      { request, confirm_switch_host: expectedIp },
      {
        onSuccess: (data) => {
          setDialogOpen(false);
          setEditing(false);
          setLastResult(
            data.ok
              ? "IP configuration applied. Your session may drop — reconnect using the new address."
              : "Request accepted without confirmation.",
          );
        },
      },
    );
  };

  const errorMessage =
    mutation.error instanceof Error ? mutation.error.message : null;

  const body = (
    <div className="space-y-3">
      <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
        <p className="font-semibold">Lockout risk</p>
        <p className="mt-1">
          Changing the management IP / VLAN / DHCP mode can disconnect you
          immediately. Verify you have console or SSH access to the switch
          before saving, and remember the new address — the web UI will not
          follow you across an IP change.
        </p>
      </div>
      <div className="rounded border border-border bg-muted p-3 text-sm">
        <p className="font-semibold">Proposed</p>
        <dl className="mt-1 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-0.5">
          <dt className="text-muted-foreground">VLAN</dt>
          <dd className="font-mono">{vlanId}</dd>
          <dt className="text-muted-foreground">Mode</dt>
          <dd>{modeLabel(mode)}</dd>
          <dt className="text-muted-foreground">Gateway</dt>
          <dd className="font-mono">{gateway || "(empty)"}</dd>
        </dl>
      </div>
    </div>
  );

  const confirmationHint = (
    <>
      Expected:{" "}
      {expectedIp ? (
        <span className="font-mono text-foreground">{expectedIp}</span>
      ) : (
        <span className="italic">loading identity…</span>
      )}
    </>
  );

  return (
    <>
      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            IP configuration
          </h4>
          {query.isLoading && (
            <span className="text-xs text-muted-foreground">Loading…</span>
          )}
        </div>

        {query.isLoading && (
          <div className="grid gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-8 animate-pulse rounded border border-border bg-muted"
              />
            ))}
          </div>
        )}

        {query.error instanceof Error && (
          <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
            <p className="font-medium">Failed to load IP configuration</p>
            <p className="mt-1 break-all">{query.error.message}</p>
            <button
              type="button"
              onClick={() => query.refetch()}
              className="mt-2 rounded-md border border-red-400 dark:border-red-900 bg-card px-3 py-1.5 text-sm font-medium text-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
            >
              Retry
            </button>
          </div>
        )}

        {query.data && !editing && (
          <>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 text-sm">
              <dt className="text-muted-foreground">VLAN</dt>
              <dd className="font-mono text-foreground">
                {query.data.vlan_id}
              </dd>
              <dt className="text-muted-foreground">Mode</dt>
              <dd className="text-foreground">{modeLabel(query.data.mode)}</dd>
              <dt className="text-muted-foreground">IP address</dt>
              <dd className="font-mono text-foreground">
                {query.data.ip_address ?? "—"}
              </dd>
              <dt className="text-muted-foreground">Subnet mask</dt>
              <dd className="font-mono text-foreground">
                {query.data.subnet_mask ?? "—"}
              </dd>
              <dt className="text-muted-foreground">Gateway</dt>
              <dd className="font-mono text-foreground">
                {query.data.gateway}
              </dd>
            </dl>
            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={handleEdit}
                className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground shadow-sm hover:bg-muted"
              >
                Edit…
              </button>
              {lastResult && (
                <span className="text-sm italic text-foreground">
                  {lastResult}
                </span>
              )}
            </div>
          </>
        )}

        {query.data && editing && (
          <>
            <div className="mb-3 rounded-md border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 p-3 text-sm text-amber-900 dark:text-amber-300">
              <p className="font-semibold">Heads up</p>
              <p className="mt-1">
                Changing the management IP may disconnect you. Verify you have
                console access before saving.
              </p>
            </div>

            <div className="grid gap-3">
              <div>
                <label className="block text-xs font-medium text-foreground">
                  Address assignment
                </label>
                <div className="mt-1 flex flex-wrap items-center gap-4 text-sm">
                  <label className="flex items-center gap-1.5">
                    <input
                      type="radio"
                      name="ip-mode"
                      checked={mode === MODE_MANUAL}
                      onChange={() => setMode(MODE_MANUAL)}
                    />
                    Manual (static)
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="radio"
                      name="ip-mode"
                      checked={mode === MODE_DHCP}
                      onChange={() => setMode(MODE_DHCP)}
                    />
                    DHCP / Bootp
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="radio"
                      name="ip-mode"
                      checked={mode === MODE_DISABLED}
                      onChange={() => setMode(MODE_DISABLED)}
                    />
                    Disabled
                  </label>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="ip-vlan"
                    className="block text-xs font-medium text-foreground"
                  >
                    VLAN
                  </label>
                  <input
                    id="ip-vlan"
                    type="number"
                    min={1}
                    max={4094}
                    value={vlanId}
                    onChange={(e) => setVlanId(Number(e.target.value) || 1)}
                    className="mt-1 w-full rounded-md border border-border px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label
                    htmlFor="ip-gateway"
                    className="block text-xs font-medium text-foreground"
                  >
                    Gateway
                  </label>
                  <input
                    id="ip-gateway"
                    type="text"
                    value={gateway}
                    placeholder="e.g. 192.168.1.1"
                    onChange={(e) => setGateway(e.target.value)}
                    className="mt-1 w-full rounded-md border border-border px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                The switch does not let the web UI edit the IP address / subnet
                mask directly — those are set via the VLAN-interface form.
                They are shown read-only in the summary above.
              </p>
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={handleSave}
                disabled={
                  !expectedIp || mutation.isPending || !gateway.trim()
                }
                className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
              >
                Save (dangerous)…
              </button>
              <button
                type="button"
                onClick={handleCancel}
                disabled={mutation.isPending}
                className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </section>

      <DangerConfirmDialog
        open={dialogOpen}
        title="Apply IP configuration change"
        body={body}
        confirmationValue={expectedIp}
        confirmationLabel="Type the switch IP to confirm"
        confirmationHint={confirmationHint}
        confirmationPlaceholder="e.g. 192.168.1.10"
        confirmButtonText="Apply IP change"
        busyButtonText="Applying…"
        onConfirm={handleConfirm}
        onCancel={() => setDialogOpen(false)}
        busy={mutation.isPending}
        error={
          errorMessage ? (
            <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
              <p className="font-semibold">Apply failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          ) : null
        }
      />
    </>
  );
}
