/**
 * VlanMembershipCard — per-port membership editor for one VLAN.
 *
 * Mirrors the legacy applet's VLAN modify panel: every port with a mode
 * select (Auto/No · Tagged · Untagged · Forbid — mode 0 is labelled "Auto"
 * when GVRP is on, "No" when off, same wire value either way). Only ports
 * whose mode actually changed are submitted (the applet's
 * `getChangedPortsID` behaviour; the switch may reject no-op updates).
 *
 * LOCKOUT RISK: removing the untagged membership of the port your own
 * client reaches the switch through cuts this UI off mid-request. Apply
 * goes through the shared DangerConfirmDialog listing the exact diff.
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useIdentity } from "@/api/hooks/useIdentity";
import { useServerSync } from "@/lib/useServerSync";
import {
  useSetVlanPorts,
  useVlanPorts,
  type VlanMembership,
} from "@/api/hooks/useVlans";

const MODE_VALUES = [0, 1, 2, 3] as const;

function modeLabel(mode: number, gvrpEnable: boolean): string {
  switch (mode) {
    case 0:
      return gvrpEnable ? "Auto" : "No";
    case 1:
      return "Tagged";
    case 2:
      return "Untagged";
    case 3:
      return "Forbid";
    default:
      return `mode ${mode}`;
  }
}

export function VlanMembershipCard({ vlanId }: { vlanId: number | null }) {
  const identity = useIdentity();
  const portsQuery = useVlanPorts(vlanId);
  const setPorts = useSetVlanPorts();

  // Draft modes keyed by port_id; reseeded whenever fresh membership data
  // arrives (selection change or post-apply refetch).
  const [draft, setDraft] = useState<Record<number, number>>({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  useServerSync(portsQuery.data, (data) => {
    setDraft(
      Object.fromEntries(data.ports.map((p) => [p.port_id, p.mode])),
    );
    setLastResult(null);
  });

  const expectedIp = identity.data?.ip_address ?? "";
  const data = portsQuery.data;
  const gvrpEnable = data?.gvrp_enable ?? false;

  const changes: Array<{ port: VlanMembership; mode: number }> = (
    data?.ports ?? []
  )
    .filter((p) => draft[p.port_id] !== undefined && draft[p.port_id] !== p.mode)
    .map((p) => ({ port: p, mode: draft[p.port_id] }));

  const handleApply = () => {
    setLastResult(null);
    setPorts.reset();
    setDialogOpen(true);
  };

  const handleRevert = () => {
    if (!data) return;
    setDraft(
      Object.fromEntries(data.ports.map((p) => [p.port_id, p.mode])),
    );
    setLastResult(null);
    setPorts.reset();
  };

  const handleConfirm = () => {
    if (!expectedIp || vlanId === null || changes.length === 0) return;
    setPorts.mutate(
      {
        vlanId,
        body: {
          request: {
            vlan_id: vlanId,
            changes: changes.map((c) => ({
              port_id: c.port.port_id,
              mode: c.mode,
            })),
          },
          confirm_switch_host: expectedIp,
        },
      },
      {
        onSuccess: () => {
          setDialogOpen(false);
          setLastResult(
            `Applied ${changes.length} membership change${
              changes.length === 1 ? "" : "s"
            } on VLAN ${vlanId}.`,
          );
        },
      },
    );
  };

  const errorMessage = apiErrorMessage(setPorts.error);

  if (vlanId === null) {
    return (
      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Port membership
        </h4>
        <p className="mt-3 text-sm text-muted-foreground">
          Select a VLAN above to view and edit its per-port membership.
        </p>
      </section>
    );
  }

  const dialogBody = (
    <div className="space-y-3">
      <ErrorBanner title="Lockout risk">
        Membership changes apply immediately. Removing the untagged
        membership of the port your own client reaches the switch through
        cuts off this UI mid-request — make sure an alternative management
        path exists before applying.
      </ErrorBanner>
      <div className="rounded border border-border bg-muted p-3 text-sm">
        <p className="font-semibold">
          VLAN {vlanId} — {changes.length} change
          {changes.length === 1 ? "" : "s"}:
        </p>
        <ul className="mt-1 space-y-0.5">
          {changes.map((c) => (
            <li key={c.port.port_id} className="font-mono text-xs">
              port {c.port.port_name}:{" "}
              {modeLabel(c.port.mode, gvrpEnable)} →{" "}
              {modeLabel(c.mode, gvrpEnable)}
            </li>
          ))}
        </ul>
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
            Port membership — VLAN {vlanId}
          </h4>
          {portsQuery.isLoading && (
            <span className="text-xs text-muted-foreground">Loading…</span>
          )}
        </div>

        {portsQuery.error instanceof Error && (
          <ErrorBanner className="mb-3">
            Failed to fetch membership: {portsQuery.error.message}
          </ErrorBanner>
        )}

        {data && (
          <>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3 lg:grid-cols-4">
              {data.ports.map((p) => {
                const current = draft[p.port_id] ?? p.mode;
                const dirty = current !== p.mode;
                return (
                  <label
                    key={p.port_id}
                    className={`flex items-center justify-between gap-2 rounded px-2 py-1 text-sm ${
                      dirty ? "bg-accent font-medium" : ""
                    }`}
                  >
                    <span className="font-mono text-xs">{p.port_name}</span>
                    <select
                      value={current}
                      onChange={(e) =>
                        setDraft((prev) => ({
                          ...prev,
                          [p.port_id]: Number(e.target.value),
                        }))
                      }
                      className="rounded-md border border-border bg-card px-2 py-1 text-xs"
                    >
                      {MODE_VALUES.map((m) => (
                        <option key={m} value={m}>
                          {modeLabel(m, gvrpEnable)}
                        </option>
                      ))}
                    </select>
                  </label>
                );
              })}
            </div>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                {changes.length === 0
                  ? "No pending changes."
                  : `${changes.length} pending change${
                      changes.length === 1 ? "" : "s"
                    } (highlighted).`}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleRevert}
                  disabled={changes.length === 0 || setPorts.isPending}
                  className="rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
                >
                  Revert
                </button>
                <button
                  type="button"
                  onClick={handleApply}
                  disabled={
                    changes.length === 0 || !expectedIp || setPorts.isPending
                  }
                  className="rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
                >
                  Apply changes (dangerous)…
                </button>
              </div>
            </div>
          </>
        )}

        {lastResult && (
          <p className="mt-3 text-sm italic text-foreground">{lastResult}</p>
        )}
      </section>

      <DangerConfirmDialog
        open={dialogOpen}
        title="Apply VLAN membership changes"
        body={dialogBody}
        confirmationValue={expectedIp}
        confirmationLabel="Type the switch IP to confirm"
        confirmationHint={confirmationHint}
        confirmationPlaceholder="e.g. 192.168.1.10"
        confirmButtonText="Apply membership changes"
        busyButtonText="Applying…"
        onConfirm={handleConfirm}
        onCancel={() => setDialogOpen(false)}
        busy={setPorts.isPending}
        error={
          errorMessage ? (
            <ErrorBanner title="Apply failed">{errorMessage}</ErrorBanner>
          ) : null
        }
      />
    </>
  );
}
