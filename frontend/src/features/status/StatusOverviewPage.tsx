/**
 * Status overview dashboard — the "default" landing page for operational
 * monitoring of the switch.
 *
 * Structure, top to bottom:
 *   1. SwitchSvg chassis (rendered only once port data has loaded so we
 *      don't flicker an empty panel on first paint)
 *   2. A 4-tile summary grid: ports-up / ports-problematic / CPU / uptime
 *   3. Recent alerts table (newest first, capped at 10 rows)
 *      with checkbox selection + Open / Ack / Delete action bar.
 *
 * Alert-log actions:
 *   * Selection state is local (useState<Set<string>>) keyed by row_id —
 *     this survives re-renders driven by the 30 s alert-log refetch.
 *   * "Open Event" is enabled when exactly one row is selected; it opens
 *     `AlertDetailDialog` which loads `/api/v1/status/alerts/{idx}?dt=<ts>`.
 *   * Ack / Delete are enabled when ≥ 1 row is selected. Delete uses
 *     `window.confirm` (no DangerConfirmDialog needed — fault-log mutations
 *     are not lockout-capable). Both invalidate the `["status", "alert-log"]`
 *     query so the table refreshes after the mutation completes.
 *
 * The identity hook is reused for uptime because the status banner endpoint
 * doesn't carry it — see DeviceStatusBanner in the generated schema. This
 * doesn't add a new request in practice because useIdentity is already
 * resolved from TopBar.
 */
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  useAcknowledgeAlerts,
  useAlertLog,
  useDeleteAlerts,
  useDeviceStatus,
  usePortStatus,
  usePortUsage,
} from "@/api/hooks/useStatus";
import { useIdentity } from "@/api/hooks/useIdentity";
import { SwitchSvg } from "@/components/switch-panel/SwitchSvg";
import { PortUtilizationChart } from "./PortUtilizationChart";
import { AlertDetailDialog } from "./AlertDetailDialog";
import { formatUptime } from "@/lib/format";
import { formatAlertTimestamp } from "@/lib/format-alert";

export function StatusOverviewPage() {
  const portsQuery = usePortStatus();
  const usageQuery = usePortUsage();
  const deviceQuery = useDeviceStatus();
  const alertsQuery = useAlertLog();
  const identityQuery = useIdentity();
  const ackMutation = useAcknowledgeAlerts();
  const delMutation = useDeleteAlerts();

  const ports = portsQuery.data?.ports;

  const { portsUp, portsProblem } = useMemo(() => {
    if (!ports) return { portsUp: 0, portsProblem: 0 };
    let up = 0;
    let problem = 0;
    for (const p of ports) {
      if (p.link_status === "Up") up++;
      else if (p.enabled) problem++;
    }
    return { portsUp: up, portsProblem: problem };
  }, [ports]);

  const recentAlerts = useMemo(() => {
    const events = alertsQuery.data?.events ?? [];
    // Newest first, capped at 10.
    return [...events]
      .sort((a, b) => b.ts_centiseconds - a.ts_centiseconds)
      .slice(0, 10);
  }, [alertsQuery.data]);

  // Selection state. Keyed by row_id so it survives re-renders driven by
  // the 30 s alert-log refetch, but we prune ids that no longer exist
  // after each refetch so a delete doesn't leave dangling selections.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const validIds = useMemo(
    () => new Set(recentAlerts.map((a) => a.row_id)),
    [recentAlerts],
  );
  const effectiveSelected = useMemo(() => {
    const out = new Set<string>();
    for (const id of selectedIds) if (validIds.has(id)) out.add(id);
    return out;
  }, [selectedIds, validIds]);
  const selectedCount = effectiveSelected.size;

  const [detailTarget, setDetailTarget] = useState<{
    index: number;
    tsCenti: number;
  } | null>(null);

  const toggleId = (rowId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(rowId)) next.delete(rowId);
      else next.add(rowId);
      return next;
    });
  };
  const toggleAll = () => {
    if (effectiveSelected.size === recentAlerts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(recentAlerts.map((a) => a.row_id)));
    }
  };

  const selectedRefs = useMemo(
    () =>
      recentAlerts
        .filter((a) => effectiveSelected.has(a.row_id))
        .map((a) => ({
          row_id: a.row_id,
          ts_centiseconds: a.ts_centiseconds,
        })),
    [recentAlerts, effectiveSelected],
  );

  const handleOpenEvent = () => {
    if (selectedRefs.length !== 1) return;
    const ref = selectedRefs[0]!;
    const idx = Number.parseInt(ref.row_id, 10);
    if (!Number.isFinite(idx)) return;
    setDetailTarget({ index: idx, tsCenti: ref.ts_centiseconds });
  };

  const handleAck = () => {
    if (selectedRefs.length === 0) return;
    ackMutation.mutate(
      { events: selectedRefs },
      {
        onSuccess: () => setSelectedIds(new Set()),
      },
    );
  };

  const handleDelete = () => {
    if (selectedRefs.length === 0) return;
    const msg =
      selectedRefs.length === 1
        ? "Delete the selected event?"
        : `Delete the ${selectedRefs.length} selected events?`;
    if (!window.confirm(msg)) return;
    delMutation.mutate(
      { events: selectedRefs },
      {
        onSuccess: () => setSelectedIds(new Set()),
      },
    );
  };

  const mutating = ackMutation.isPending || delMutation.isPending;
  const mutationError =
    (ackMutation.error instanceof Error ? ackMutation.error.message : null) ??
    (delMutation.error instanceof Error ? delMutation.error.message : null);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Status</h2>
        <button
          type="button"
          onClick={() => {
            portsQuery.refetch();
            usageQuery.refetch();
            deviceQuery.refetch();
            alertsQuery.refetch();
            identityQuery.refetch();
          }}
          disabled={portsQuery.isFetching || deviceQuery.isFetching}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
        >
          {portsQuery.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* Chassis */}
      <section className="mb-6 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
        {portsQuery.isLoading && (
          <div className="h-40 animate-pulse rounded bg-neutral-100" />
        )}
        {portsQuery.isError && (
          <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">
            Failed to load port status:{" "}
            {portsQuery.error instanceof Error
              ? portsQuery.error.message
              : String(portsQuery.error)}
          </div>
        )}
        {ports && (
          <>
            <SwitchSvg ports={ports} />
            <Legend />
          </>
        )}
      </section>

      {/* Port utilisation chart (parity with the legacy applet) */}
      <section className="mb-6 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
        {usageQuery.isLoading && (
          <div className="h-40 animate-pulse rounded bg-neutral-100" />
        )}
        {usageQuery.isError && (
          <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">
            Failed to load port utilisation:{" "}
            {usageQuery.error instanceof Error
              ? usageQuery.error.message
              : String(usageQuery.error)}
          </div>
        )}
        {usageQuery.data && (
          <PortUtilizationChart
            usage={usageQuery.data.ports}
            portStatus={ports}
          />
        )}
      </section>

      {/* Summary cards */}
      <section className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Ports up"
          value={ports ? String(portsUp) : "—"}
          sub={ports ? `${ports.length} total` : undefined}
        />
        <SummaryCard
          label="Down but enabled"
          value={ports ? String(portsProblem) : "—"}
          sub="Link Down on an enabled port"
          tone={portsProblem > 0 ? "warn" : "ok"}
        />
        <SummaryCard
          label="CPU"
          value={
            identityQuery.data ? `${identityQuery.data.cpu_pct}%` : "—"
          }
          sub={
            deviceQuery.data?.state
              ? `Banner: ${deviceQuery.data.state}`
              : undefined
          }
        />
        <SummaryCard
          label="Uptime"
          value={
            identityQuery.data
              ? formatUptime(identityQuery.data.uptime_centiseconds)
              : "—"
          }
        />
      </section>

      {/* Recent alerts */}
      <section className="rounded-lg border border-neutral-200 bg-white shadow-sm">
        <header className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
            Recent alerts
          </h3>
          {alertsQuery.data && (
            <span className="text-xs text-neutral-500">
              Showing {recentAlerts.length} of {alertsQuery.data.events.length}
            </span>
          )}
        </header>

        {/* Action bar */}
        {alertsQuery.data && recentAlerts.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-neutral-100 bg-neutral-50/60 px-4 py-2">
            <span className="text-xs text-neutral-600">
              {selectedCount === 0
                ? "Select rows to act on them."
                : `${selectedCount} selected`}
            </span>
            <div className="ml-auto flex flex-wrap gap-2">
              <ActionButton
                onClick={handleOpenEvent}
                disabled={selectedCount !== 1 || mutating}
              >
                Open Event
              </ActionButton>
              <ActionButton
                onClick={handleAck}
                disabled={selectedCount === 0 || mutating}
                busy={ackMutation.isPending}
                busyLabel="Acknowledging…"
              >
                Acknowledge selected
              </ActionButton>
              <ActionButton
                onClick={handleDelete}
                disabled={selectedCount === 0 || mutating}
                busy={delMutation.isPending}
                busyLabel="Deleting…"
                tone="danger"
              >
                Delete selected
              </ActionButton>
            </div>
          </div>
        )}
        {mutationError && (
          <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-900">
            {mutationError}
          </div>
        )}

        {alertsQuery.isLoading && (
          <div className="p-4">
            <div className="h-24 animate-pulse rounded bg-neutral-100" />
          </div>
        )}
        {alertsQuery.isError && (
          <div className="p-4 text-sm text-red-900">
            Failed to load alert log:{" "}
            {alertsQuery.error instanceof Error
              ? alertsQuery.error.message
              : String(alertsQuery.error)}
          </div>
        )}
        {alertsQuery.data && recentAlerts.length === 0 && (
          <div className="p-4 text-sm text-neutral-500">
            No alerts reported.
          </div>
        )}
        {alertsQuery.data && recentAlerts.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-neutral-50 text-left text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="w-10 px-4 py-2">
                    <input
                      type="checkbox"
                      aria-label="Select all rows"
                      checked={
                        recentAlerts.length > 0 &&
                        effectiveSelected.size === recentAlerts.length
                      }
                      ref={(el) => {
                        if (el) {
                          el.indeterminate =
                            effectiveSelected.size > 0 &&
                            effectiveSelected.size < recentAlerts.length;
                        }
                      }}
                      onChange={toggleAll}
                    />
                  </th>
                  <th className="px-4 py-2 font-semibold">When</th>
                  <th className="px-4 py-2 font-semibold">Category</th>
                  <th className="px-4 py-2 font-semibold">Alert</th>
                  <th className="px-4 py-2 font-semibold">Description</th>
                </tr>
              </thead>
              <tbody>
                {recentAlerts.map((e) => {
                  const checked = effectiveSelected.has(e.row_id);
                  return (
                    <tr
                      key={e.row_id}
                      className={`border-t border-neutral-100 align-top ${
                        checked ? "bg-blue-50/40" : ""
                      }`}
                    >
                      <td className="px-4 py-2">
                        <input
                          type="checkbox"
                          aria-label={`Select event ${e.row_id}`}
                          checked={checked}
                          onChange={() => toggleId(e.row_id)}
                        />
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-neutral-600">
                        {formatAlertTimestamp(
                          e.ts_centiseconds,
                          identityQuery.data?.uptime_centiseconds,
                        )}
                      </td>
                      <td className="px-4 py-2 text-neutral-700">
                        {e.category || "—"}
                      </td>
                      <td className="px-4 py-2 font-medium text-neutral-900">
                        {e.alert_name}
                      </td>
                      <td className="px-4 py-2 text-neutral-700">
                        {e.description}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <AlertDetailDialog
        index={detailTarget?.index ?? null}
        tsCenti={detailTarget?.tsCenti ?? null}
        currentUptimeCenti={identityQuery.data?.uptime_centiseconds}
        onClose={() => setDetailTarget(null)}
      />
    </div>
  );
}

function Legend() {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-neutral-600">
      <LegendDot color="#22c55e" label="Up" />
      <LegendDot color="#f59e0b" label="Down (enabled)" />
      <LegendDot color="#a3a3a3" label="Disabled / no data" />
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="inline-block h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "ok" | "warn";
}) {
  const valueColor =
    tone === "warn" ? "text-amber-700" : "text-neutral-900";
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-semibold ${valueColor}`}>
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-neutral-500">{sub}</div>}
    </div>
  );
}

function ActionButton({
  onClick,
  disabled,
  busy = false,
  busyLabel,
  tone,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  busyLabel?: string;
  tone?: "danger";
  children: ReactNode;
}) {
  const base =
    "rounded-md border px-3 py-1.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed";
  const palette =
    tone === "danger"
      ? "border-red-300 text-red-800 hover:bg-red-50"
      : "border-neutral-300 text-neutral-700 hover:bg-neutral-50";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${palette}`}
    >
      {busy && busyLabel ? busyLabel : children}
    </button>
  );
}
