/**
 * Per-port detail page reached from the Status chassis or the ports table.
 *
 * Layout:
 *   1. Header card — port number, human name, link state, enabled flag,
 *      current line mode (e.g. "1000FDx"), and a back link to /status.
 *   2. Live chart — packets-in/out/s over a rolling 2-minute window fed by
 *      the /ws/port-traffic WebSocket (see LivePortChart).
 *   3. Counter totals table — running Rx/Tx / mcast / bcast / errors from
 *      the /api/v1/status/counters poll. We render totals (not rates); the
 *      chart covers the rate view.
 *
 * The route file already hands us `port` as a string (route-parameter); we
 * coerce to a number once here and bail early if it isn't a finite integer,
 * so downstream hooks never see NaN.
 *
 * Phase 2 note: VLAN memberships are not available from any read-only
 * endpoint in Phase 2 (they live behind /cgi/vid_* configuration writes).
 * We surface this as a clearly labelled placeholder rather than silently
 * omitting it, so admins don't wonder if the row is missing data.
 */
import { apiErrorMessage } from "@/api/client";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Link } from "@tanstack/react-router";
import { usePortStatus, usePortCounters } from "@/api/hooks/useStatus";
import { LivePortChart } from "./LivePortChart";
import type { components } from "@/api/schema";

type PortStatus = components["schemas"]["PortStatus"];
type PortCounters = components["schemas"]["PortCounters"];

export function PortDetailPage({ port: portStr }: { port: string }) {
  const portNum = Number(portStr);
  const portIsValid = Number.isFinite(portNum) && Number.isInteger(portNum) && portNum > 0;

  // Switch read-safety: this page already streams live rates for the port
  // over the WebSocket (2 s cadence in LivePortChart), so the REST polls
  // here are slowed way down — the default 5 s/10 s cadences would
  // double-poll the same /cgi/portc data the stream is delivering. Link
  // mode rarely changes and counter TOTALS only need a coarse refresh (the
  // manual Refresh button covers impatience).
  const portsQuery = usePortStatus({ refetchInterval: 30_000 });
  const countersQuery = usePortCounters({ refetchInterval: 60_000 });

  const portStatus: PortStatus | undefined = portIsValid
    ? portsQuery.data?.ports.find((p) => p.port === portNum)
    : undefined;
  const counters: PortCounters | undefined = portIsValid
    ? countersQuery.data?.ports.find((p) => p.port === portNum)
    : undefined;

  if (!portIsValid) {
    return (
      <div className="p-6">
        <BackLink />
        <ErrorBanner className="mt-4">
          Invalid port id: <code className="font-mono">{portStr}</code>
        </ErrorBanner>
      </div>
    );
  }

  // We only show "port not found" once the parent status query has actually
  // resolved — otherwise the first paint briefly shows a 404 for legitimate
  // ports while the request is still in flight.
  const notFound =
    portsQuery.data !== undefined &&
    portStatus === undefined;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <BackLink />
        <button
          type="button"
          onClick={() => {
            portsQuery.refetch();
            countersQuery.refetch();
          }}
          disabled={portsQuery.isFetching || countersQuery.isFetching}
          className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
        >
          {portsQuery.isFetching || countersQuery.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <HeaderCard
        portNum={portNum}
        portStatus={portStatus}
        loading={portsQuery.isLoading}
        error={portsQuery.error}
        notFound={notFound}
      />

      {portStatus && <LivePortChart port={portNum} />}

      <CountersCard
        counters={counters}
        loading={countersQuery.isLoading}
        error={countersQuery.error}
        available={!!portStatus}
      />

      <VlanCard />
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/status"
      className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 dark:text-blue-300 hover:underline"
    >
      <span aria-hidden>&larr;</span> Back to status
    </Link>
  );
}

function HeaderCard({
  portNum,
  portStatus,
  loading,
  error,
  notFound,
}: {
  portNum: number;
  portStatus: PortStatus | undefined;
  loading: boolean;
  error: unknown;
  notFound: boolean;
}) {
  if (loading) {
    return (
      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="mt-3 h-5 w-64 animate-pulse rounded bg-muted" />
      </section>
    );
  }
  if (error) {
    return (
      <ErrorBanner>
        Failed to load port status: {apiErrorMessage(error)}
      </ErrorBanner>
    );
  }
  if (notFound || !portStatus) {
    return (
      <section className="rounded-md border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 p-3 text-sm text-amber-900 dark:text-amber-300">
        Port {portNum} not found on this switch.
      </section>
    );
  }

  const linkUp = portStatus.link_status === "Up";
  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="text-xl font-semibold text-foreground">
          Port {portStatus.port}
        </h2>
        {portStatus.port_name && (
          <span className="text-base text-muted-foreground">
            {portStatus.port_name}
          </span>
        )}
        <StateBadge linkUp={linkUp} enabled={portStatus.enabled} />
      </div>
      <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Link" value={portStatus.link_status} />
        <Field label="Enabled" value={portStatus.enabled ? "Yes" : "No"} />
        <Field label="Current mode" value={portStatus.current_mode || "—"} />
        <Field label="Type" value={portStatus.port_type || "—"} />
        <Field label="Flow control" value={portStatus.flow_ctrl || "—"} />
        <Field label="Trunk" value={portStatus.trunk || "—"} />
        <Field
          label="Type label"
          value={portStatus.port_type_label?.trim() || "—"}
        />
      </dl>
    </section>
  );
}

function StateBadge({ linkUp, enabled }: { linkUp: boolean; enabled: boolean }) {
  let cls: string;
  let label: string;
  if (linkUp) {
    cls = "bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300";
    label = "Link up";
  } else if (enabled) {
    cls = "bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300";
    label = "Link down";
  } else {
    cls = "bg-muted text-foreground";
    label = "Disabled";
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {label}
    </span>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 font-medium text-foreground">{value}</dd>
    </div>
  );
}

function CountersCard({
  counters,
  loading,
  error,
  available,
}: {
  counters: PortCounters | undefined;
  loading: boolean;
  error: unknown;
  available: boolean;
}) {
  return (
    <section className="rounded-lg border border-border bg-card shadow-sm">
      <header className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Counter totals
        </h3>
      </header>
      <div className="p-4">
        {loading && (
          <div className="h-24 animate-pulse rounded bg-muted" />
        )}
        {error != null && (
          <div className="text-sm text-red-900">
            Failed to load counters:{" "}
            {apiErrorMessage(error)}
          </div>
        )}
        {!loading && error == null && (!counters || !available) && (
          <div className="text-sm text-muted-foreground">
            No counter data available for this port.
          </div>
        )}
        {counters && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-semibold">Metric</th>
                  <th className="px-4 py-2 text-right font-semibold">Rx</th>
                  <th className="px-4 py-2 text-right font-semibold">Tx</th>
                </tr>
              </thead>
              <tbody>
                <CounterRow label="Packets" rx={counters.pkts_rx} tx={counters.pkts_tx} />
                <CounterRow label="Multicast" rx={counters.mcast_rx} tx={counters.mcast_tx} />
                <CounterRow label="Broadcast" rx={counters.bcast_rx} tx={counters.bcast_tx} />
                <CounterRow label="Errors" rx={counters.errors_rx} tx={null} />
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted-foreground">
              Counters are packet counts as reported by the switch and wrap at
              2<sup>32</sup>.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function CounterRow({
  label,
  rx,
  tx,
}: {
  label: string;
  rx: number;
  tx: number | null;
}) {
  return (
    <tr className="border-t border-border">
      <td className="px-4 py-2 font-medium text-foreground">{label}</td>
      <td className="px-4 py-2 text-right font-mono tabular-nums text-foreground">
        {rx.toLocaleString()}
      </td>
      <td className="px-4 py-2 text-right font-mono tabular-nums text-foreground">
        {tx === null ? "—" : tx.toLocaleString()}
      </td>
    </tr>
  );
}

function VlanCard() {
  return (
    <section className="rounded-lg border border-dashed border-border bg-muted p-4 text-sm text-muted-foreground">
      <div className="font-semibold text-foreground">VLAN memberships</div>
      <p className="mt-1">
        Not available in Phase 2 — VLAN membership is only exposed through the
        write-path endpoints which are not wired up yet.
      </p>
    </section>
  );
}
