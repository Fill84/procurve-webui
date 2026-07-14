/**
 * Recharts LineChart fed by `useLivePortTraffic` showing packets-in/out per
 * second on a rolling two-minute window.
 *
 * Two colour choices:
 *   - Inbound (#16a34a, green) reads as "receive / normal".
 *   - Outbound (#2563eb, blue) reads as "transmit / origin".
 * These match the defaults called out in the Task 2.12 brief and keep the
 * palette consistent with the status legend's up/down greens.
 *
 * Disconnected UX:
 *   - The connection pill at the top right always reflects live state.
 *   - When the socket is closed AND there are no samples in the buffer, we
 *     replace the chart body with a "Live feed disconnected" panel and a
 *     Reconnect button; opening a new WS will re-run the effect and start
 *     populating samples.
 *   - When the socket drops mid-stream we keep the last window visible and
 *     just flip the pill — the admin can still read history while
 *     reconnecting manually.
 *
 * Animation is disabled (`isAnimationActive={false}`) because Recharts'
 * default transform animates every point on every state update, which fights
 * with our 1–2 Hz streaming cadence and produces visible stutter.
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useLivePortTraffic } from "@/api/hooks/useLivePortTraffic";

interface LivePortChartProps {
  port: number;
  /** Rolling buffer depth in samples. Default 240 ≈ 2 min at 0.5 s poll. */
  bufferSize?: number;
}

export function LivePortChart({ port, bufferSize = 240 }: LivePortChartProps) {
  const { samples, connected, reconnect } = useLivePortTraffic(port, bufferSize);

  const showDisconnectedState = !connected && samples.length === 0;

  return (
    <section className="rounded-lg border border-border bg-card text-card-foreground shadow-sm">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Live packet rate
        </h3>
        <div className="flex items-center gap-3">
          <ConnectionPill connected={connected} />
          {!connected && (
            <button
              type="button"
              onClick={reconnect}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted"
            >
              Reconnect
            </button>
          )}
        </div>
      </header>
      <div className="p-4">
        {showDisconnectedState ? (
          <div className="flex h-[300px] flex-col items-center justify-center text-sm text-muted-foreground">
            <p>Live feed disconnected.</p>
            <button
              type="button"
              onClick={reconnect}
              className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
            >
              Reconnect
            </button>
          </div>
        ) : samples.length === 0 ? (
          <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
            Waiting for first sample…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={samples} margin={{ top: 5, right: 16, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(t: number) => formatClock(t)}
                minTickGap={40}
                stroke="hsl(var(--muted-foreground))"
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              />
              <YAxis
                allowDecimals={false}
                stroke="hsl(var(--muted-foreground))"
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                width={56}
              />
              <Tooltip
                labelFormatter={(t) => formatClock(t as number)}
                formatter={(v) => (typeof v === "number" ? v.toFixed(1) : String(v))}
                contentStyle={{
                  backgroundColor: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                  color: "hsl(var(--popover-foreground))",
                }}
                labelStyle={{ color: "hsl(var(--muted-foreground))" }}
                itemStyle={{ color: "hsl(var(--popover-foreground))" }}
              />
              <Line
                type="monotone"
                dataKey="pkts_in_per_s"
                stroke="#16a34a"
                dot={false}
                isAnimationActive={false}
                name="Packets in/s"
              />
              <Line
                type="monotone"
                dataKey="pkts_out_per_s"
                stroke="#2563eb"
                dot={false}
                isAnimationActive={false}
                name="Packets out/s"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <LegendSwatch color="#16a34a" label="Packets in/s" />
          <LegendSwatch color="#2563eb" label="Packets out/s" />
          <span className="ml-auto text-muted-foreground">
            {samples.length} / {bufferSize} samples
          </span>
        </div>
      </div>
    </section>
  );
}

function ConnectionPill({ connected }: { connected: boolean }) {
  return (
    <span
      className={
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium " +
        (connected
          ? "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-300"
          : "bg-muted text-muted-foreground")
      }
    >
      <span
        aria-hidden
        className={
          "inline-block h-2 w-2 rounded-full " +
          (connected ? "bg-green-600" : "bg-muted-foreground")
        }
      />
      {connected ? "Live" : "Disconnected"}
    </span>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="inline-block h-2.5 w-4 rounded-sm"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function formatClock(t: number): string {
  const d = new Date(t);
  if (!Number.isFinite(d.getTime())) return "";
  return d.toLocaleTimeString();
}
