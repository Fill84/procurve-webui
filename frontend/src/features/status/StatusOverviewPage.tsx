/**
 * Status overview dashboard — the "default" landing page for operational
 * monitoring of the switch.
 *
 * Structure, top to bottom:
 *   1. SwitchSvg chassis (rendered only once port data has loaded so we
 *      don't flicker an empty panel on first paint)
 *   2. A 4-tile summary grid: ports-up / ports-problematic / CPU / uptime
 *   3. Recent alerts table (newest first, capped at 10 rows)
 *      with checkbox selection + Ack / Delete action bar.
 *
 * Alert-log actions:
 *   * Selection state is local (useState<Set<string>>) keyed by row_id —
 *     this survives re-renders driven by the 30 s alert-log refetch.
 *   * Clicking anywhere on a row (outside the checkbox) opens
 *     `AlertDetailDialog`, which loads `/api/v1/status/alerts/{idx}?dt=<ts>`.
 *     The checkbox is the selection affordance; the rest of the row is
 *     the "open" affordance. There is no separate Open Event button.
 *   * Ack / Delete are enabled when ≥ 1 row is selected. Delete shows a
 *     `ConfirmDialog` first (no DangerConfirmDialog — fault-log mutations
 *     are not lockout-capable, so typed-IP friction would be excessive).
 *     Both invalidate the `["status", "alert-log"]` query so the table
 *     refreshes after the mutation completes.
 *   * Ack on this firmware does NOT remove rows — the switch keeps acked
 *     events in the list (per ack_alerts.md: it's a "seen" flag, not a
 *     deletion). To make a successful ack visible we surface a transient
 *     "N event(s) acknowledged" banner; otherwise the user clicks Ack and
 *     sees no observable change in the table, which reads as "broken".
 *
 * The identity hook is reused for uptime because the status banner endpoint
 * doesn't carry it — see DeviceStatusBanner in the generated schema. This
 * doesn't add a new request in practice because useIdentity is already
 * resolved from TopBar.
 */
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
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
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { PortUtilizationChart } from "./PortUtilizationChart";
import { AlertDetailDialog } from "./AlertDetailDialog";
import { formatUptime } from "@/lib/format";
import { formatAlertTimestamp } from "@/lib/format-alert";
import { useLiveUptime } from "@/lib/utils";

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

  // Call hook unconditionally, outside of JSX
  const liveUptime = useLiveUptime(
    formatUptime,
    identityQuery.data?.uptime_centiseconds ?? 0,
  );

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

  // Confirm-dialog state for the destructive Delete action. We open this
  // instead of `window.confirm` so the dialog matches the rest of the app's
  // chrome (and renders consistently in the dev container's headless tests).
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  // Transient post-ack feedback. The fault log keeps acked rows visible, so
  // without this banner a successful Acknowledge produces no observable UI
  // change and reads as "didn't work". `null` means no message; the count
  // is reset after a few seconds so the banner doesn't linger.
  const [ackedCount, setAckedCount] = useState<number | null>(null);
  useEffect(() => {
    if (ackedCount === null) return;
    const id = window.setTimeout(() => setAckedCount(null), 5000);
    return () => window.clearTimeout(id);
  }, [ackedCount]);

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

  const openDetailFor = (rowId: string, tsCenti: number) => {
    const idx = Number.parseInt(rowId, 10);
    if (!Number.isFinite(idx)) return;
    setDetailTarget({ index: idx, tsCenti });
  };

  const handleAck = () => {
    if (selectedRefs.length === 0) return;
    const count = selectedRefs.length;
    ackMutation.mutate(
      { events: selectedRefs },
      {
        onSuccess: () => {
          setSelectedIds(new Set());
          setAckedCount(count);
        },
      },
    );
  };

  const handleDelete = () => {
    if (selectedRefs.length === 0) return;
    setDeleteConfirmOpen(true);
  };

  const confirmDelete = () => {
    if (selectedRefs.length === 0) {
      setDeleteConfirmOpen(false);
      return;
    }
    delMutation.mutate(
      { events: selectedRefs },
      {
        onSuccess: () => {
          setSelectedIds(new Set());
          setDeleteConfirmOpen(false);
        },
        onError: () => {
          // Keep the dialog open so the user sees the error in-context.
        },
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
          className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
        >
          {portsQuery.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* Chassis */}
      <section className="mb-6 rounded-lg border border-border bg-card p-4 shadow-sm">
        {portsQuery.isLoading && (
          <div className="h-40 animate-pulse rounded bg-muted" />
        )}
        {portsQuery.isError && (
          <div className="rounded border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
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
      <section className="mb-6 rounded-lg border border-border bg-card p-4 shadow-sm">
        {usageQuery.isLoading && (
          <div className="h-40 animate-pulse rounded bg-muted" />
        )}
        {usageQuery.isError && (
          <div className="rounded border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
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
              ? liveUptime
              : "—"
          }
        />
      </section>

      {/* Recent alerts */}
      <section className="rounded-lg border border-border bg-card shadow-sm">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Recent alerts
          </h3>
          {alertsQuery.data && (
            <span className="text-xs text-muted-foreground">
              Showing {recentAlerts.length} of {alertsQuery.data.events.length}
            </span>
          )}
        </header>

        {/* Action bar */}
        {alertsQuery.data && recentAlerts.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/60 px-4 py-2">
            <span className="text-xs text-muted-foreground">
              {selectedCount === 0
                ? "Click a row to view details, or tick rows to ack/delete."
                : `${selectedCount} selected`}
            </span>
            <div className="ml-auto flex flex-wrap gap-2">
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
          <div className="border-b border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-4 py-2 text-sm text-red-900 dark:text-red-300">
            {mutationError}
          </div>
        )}
        {ackedCount !== null && (
          <div
            role="status"
            className="border-b border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300"
          >
            {ackedCount === 1
              ? "1 event acknowledged. The switch keeps acked events in the log."
              : `${ackedCount} events acknowledged. The switch keeps acked events in the log.`}
          </div>
        )}

        {alertsQuery.isLoading && (
          <div className="p-4">
            <div className="h-24 animate-pulse rounded bg-muted" />
          </div>
        )}
        {alertsQuery.isError && (
          <div className="p-4 text-sm text-red-900 dark:text-red-300">
            Failed to load alert log:{" "}
            {alertsQuery.error instanceof Error
              ? alertsQuery.error.message
              : String(alertsQuery.error)}
          </div>
        )}
        {alertsQuery.data && recentAlerts.length === 0 && (
          <div className="p-4 text-sm text-muted-foreground">
            No alerts reported.
          </div>
        )}
        {alertsQuery.data && recentAlerts.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
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
                      onClick={() => openDetailFor(e.row_id, e.ts_centiseconds)}
                      onKeyDown={(ev) => {
                        if (ev.key === "Enter" || ev.key === " ") {
                          ev.preventDefault();
                          openDetailFor(e.row_id, e.ts_centiseconds);
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-label={`Open event ${e.alert_name || e.row_id}`}
                      className={`cursor-pointer border-t border-border align-top hover:bg-muted focus:bg-muted focus:outline-none ${checked ? "bg-blue-50/40 dark:bg-blue-950/40 hover:bg-blue-50/60 dark:hover:bg-blue-950/40" : ""
                        }`}
                    >
                      <td
                        className="px-4 py-2"
                        onClick={(ev) => ev.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          aria-label={`Select event ${e.row_id}`}
                          checked={checked}
                          onChange={() => toggleId(e.row_id)}
                          onClick={(ev) => ev.stopPropagation()}
                        />
                      </td>
                      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                        {formatAlertTimestamp(
                          e.ts_centiseconds,
                          identityQuery.data?.uptime_centiseconds,
                        )}
                      </td>
                      <td className="px-4 py-2 text-foreground">
                        {e.category || "—"}
                      </td>
                      <td className="px-4 py-2 font-medium text-foreground">
                        {e.alert_name}
                      </td>
                      <td className="px-4 py-2 text-foreground">
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

      <ConfirmDialog
        open={deleteConfirmOpen}
        title={
          selectedRefs.length === 1
            ? "Delete event"
            : `Delete ${selectedRefs.length} events`
        }
        body={
          <p>
            {selectedRefs.length === 1
              ? "The selected event will be removed from the switch fault log. This cannot be undone."
              : `The ${selectedRefs.length} selected events will be removed from the switch fault log. This cannot be undone.`}
          </p>
        }
        confirmLabel={
          selectedRefs.length === 1 ? "Delete event" : "Delete events"
        }
        busyLabel="Deleting…"
        tone="danger"
        busy={delMutation.isPending}
        error={
          delMutation.error instanceof Error ? (
            <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-2 text-sm text-red-900 dark:text-red-300">
              {delMutation.error.message}
            </div>
          ) : null
        }
        onConfirm={confirmDelete}
        onCancel={() => {
          if (!delMutation.isPending) setDeleteConfirmOpen(false);
        }}
      />
    </div>
  );
}

function Legend() {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
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
    tone === "warn" ? "text-amber-700 dark:text-amber-300" : "text-foreground";
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-semibold ${valueColor}`}>
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
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
      ? "border-red-300 dark:border-red-900 text-red-800 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/40"
      : "border-border text-foreground hover:bg-muted";
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
