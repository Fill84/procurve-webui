/**
 * Status overview dashboard — the "default" landing page for operational
 * monitoring of the switch.
 *
 * Structure, top to bottom:
 *   1. SwitchSvg chassis (rendered only once port data has loaded so we
 *      don't flicker an empty panel on first paint)
 *   2. A 4-tile summary grid: ports-up / ports-problematic / CPU / uptime
 *   3. Recent alerts table (newest first, capped at 10 rows)
 *
 * The identity hook is reused for uptime because the status banner endpoint
 * doesn't carry it — see DeviceStatusBanner in the generated schema. This
 * doesn't add a new request in practice because useIdentity is already
 * resolved from TopBar.
 */
import type { ReactNode } from "react";
import { useMemo } from "react";
import {
  useDeviceStatus,
  usePortStatus,
  usePortUsage,
  useAlertLog,
} from "@/api/hooks/useStatus";
import { useIdentity } from "@/api/hooks/useIdentity";
import { SwitchSvg } from "@/components/switch-panel/SwitchSvg";
import { PortUtilizationChart } from "./PortUtilizationChart";
import { formatUptime } from "@/lib/format";

export function StatusOverviewPage() {
  const portsQuery = usePortStatus();
  const usageQuery = usePortUsage();
  const deviceQuery = useDeviceStatus();
  const alertsQuery = useAlertLog();
  const identityQuery = useIdentity();

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
                  <th className="px-4 py-2 font-semibold">When</th>
                  <th className="px-4 py-2 font-semibold">Category</th>
                  <th className="px-4 py-2 font-semibold">Alert</th>
                  <th className="px-4 py-2 font-semibold">Description</th>
                </tr>
              </thead>
              <tbody>
                {recentAlerts.map((e) => (
                  <tr
                    key={e.row_id}
                    className="border-t border-neutral-100 align-top"
                  >
                    <td className="px-4 py-2 font-mono text-xs text-neutral-600">
                      {formatAlertTimestamp(e.ts_centiseconds)}
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
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
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

/**
 * Render a best-effort human timestamp for an alert event.
 *
 * The switch reports `ts_centiseconds` as a wall-clock value (centiseconds
 * since the Unix epoch on firmware with a valid clock). Multiplying by 10
 * gives milliseconds suitable for `new Date`. If the result looks obviously
 * bogus (e.g. before 2000) we fall back to the raw centisecond value so
 * the admin can still sort and inspect entries.
 */
function formatAlertTimestamp(tsCenti: number): string {
  const ms = tsCenti * 10;
  const d = new Date(ms);
  if (!Number.isFinite(d.getTime()) || d.getUTCFullYear() < 2000) {
    return `t=${tsCenti}`;
  }
  return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
}
