/**
 * Port Utilization bar chart — parity with the legacy Java applet's
 * Status Overview panel.
 *
 * Each port gets a vertical stacked bar with three segments:
 *   usage1 → "% Unicast Rx or All Tx" (blue)
 *   usage2 → "% Non-Unicast Pkts Rx"  (amber)
 *   usage3 → "% Error Packets Rx"     (magenta)
 *
 * The Y axis is percent (0-100). A small LED circle beneath each bar
 * reflects the port state letter the firmware reports:
 *   G → connected      (green)
 *   W → warning        (amber)
 *   N → not connected  (gray outline)
 *   R → error          (red)
 *
 * We also gray out bars for ports that are administratively disabled
 * (PortStatus.enabled === false) so "disabled" is distinguishable from
 * "just sitting quietly".
 */
import type { components } from "@/api/schema";

type PortUsage = components["schemas"]["PortUsage"];
type PortStatus = components["schemas"]["PortStatus"];

const COLOR_USAGE1 = "#2563eb"; // blue-600
const COLOR_USAGE2 = "#f59e0b"; // amber-500
const COLOR_USAGE3 = "#db2777"; // pink-600

const LED_COLORS: Record<PortUsage["state"], string> = {
  G: "#22c55e", // green-500
  W: "#f59e0b", // amber-500
  N: "#d4d4d8", // neutral-300
  R: "#ef4444", // red-500
};

interface Props {
  usage: PortUsage[];
  /** Optional — used to fade out admin-disabled ports. */
  portStatus?: PortStatus[];
}

export function PortUtilizationChart({ usage, portStatus }: Props) {
  const disabledSet = new Set(
    (portStatus ?? []).filter((p) => !p.enabled).map((p) => p.port),
  );

  const sorted = [...usage].sort((a, b) => a.port - b.port);

  // Chart geometry — defined in viewBox units, rendered at 100% width with
  // `preserveAspectRatio="none"` so the bars stretch horizontally to fill
  // whatever container we're in. Vertical proportions stay fixed because the
  // Y axis is a percentage.
  const topPad = 14; // headroom so the "100%" Y-axis label is not clipped
  const chartHeight = 160; // px — plotting area
  const labelHeight = 20;
  const ledHeight = 24;
  const barWidth = 28;
  const barGap = 14;
  const leftPad = 40; // room for Y-axis labels
  const rightPad = 12;
  const chartWidth =
    leftPad + rightPad + sorted.length * (barWidth + barGap) - barGap;
  const totalHeight = topPad + chartHeight + labelHeight + ledHeight;
  const plotTop = topPad;
  const plotBottom = topPad + chartHeight;

  return (
    <div className="mt-4">
      <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-600">
        Port Utilization
      </h4>

      <div className="flex flex-col gap-3 md:flex-row md:items-start">
        <div className="min-w-0 flex-1">
          <svg
            viewBox={`0 0 ${chartWidth} ${totalHeight}`}
            preserveAspectRatio="none"
            role="img"
            aria-label="Port utilisation bar chart"
            className="block w-full"
            style={{ height: `${totalHeight}px` }}
          >
            {/* Gridlines + Y-axis labels at 30, 70, 100 */}
            {[30, 70, 100].map((pct) => {
              const y = plotBottom - (pct / 100) * chartHeight;
              return (
                <g key={pct}>
                  <line
                    x1={leftPad}
                    x2={chartWidth - rightPad}
                    y1={y}
                    y2={y}
                    stroke="#e5e7eb"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  />
                  <text
                    x={leftPad - 6}
                    y={y + 3}
                    fontSize={10}
                    fill="#6b7280"
                    textAnchor="end"
                    // Keep axis text readable when the chart is stretched
                    // horizontally (preserveAspectRatio="none" would stretch
                    // default text glyphs too).
                    style={{ fontSize: "10px" }}
                    transform={`translate(0 0)`}
                  >
                    {pct}%
                  </text>
                </g>
              );
            })}

            {/* Bars + port labels + LEDs */}
            {sorted.map((p, i) => {
              const x = leftPad + i * (barWidth + barGap);
              const disabled = disabledSet.has(p.port);
              const total = Math.min(100, p.usage1 + p.usage2 + p.usage3);
              // Stack from bottom up: usage1, usage2, usage3.
              const h1 = (p.usage1 / 100) * chartHeight;
              const h2 = (p.usage2 / 100) * chartHeight;
              const h3 = (p.usage3 / 100) * chartHeight;
              const y1 = plotBottom - h1;
              const y2 = y1 - h2;
              const y3 = y2 - h3;
              const opacity = disabled ? 0.35 : 1;

              return (
                <g key={p.port}>
                  {/* Empty-bar baseline rail for readability */}
                  <rect
                    x={x}
                    y={plotTop}
                    width={barWidth}
                    height={chartHeight}
                    fill="#f9fafb"
                  />
                  {p.usage1 > 0 && (
                    <rect
                      x={x}
                      y={y1}
                      width={barWidth}
                      height={h1}
                      fill={COLOR_USAGE1}
                      opacity={opacity}
                    />
                  )}
                  {p.usage2 > 0 && (
                    <rect
                      x={x}
                      y={y2}
                      width={barWidth}
                      height={h2}
                      fill={COLOR_USAGE2}
                      opacity={opacity}
                    />
                  )}
                  {p.usage3 > 0 && (
                    <rect
                      x={x}
                      y={y3}
                      width={barWidth}
                      height={h3}
                      fill={COLOR_USAGE3}
                      opacity={opacity}
                    />
                  )}

                  {/* Baseline */}
                  <line
                    x1={x}
                    x2={x + barWidth}
                    y1={plotBottom}
                    y2={plotBottom}
                    stroke="#9ca3af"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  />

                  {/* Port number */}
                  <text
                    x={x + barWidth / 2}
                    y={plotBottom + labelHeight - 6}
                    fontSize={10}
                    fill="#374151"
                    textAnchor="middle"
                  >
                    {p.port}
                  </text>

                  {/* LED */}
                  {disabled ? (
                    <g
                      transform={`translate(${x + barWidth / 2}, ${plotBottom + labelHeight + ledHeight / 2})`}
                    >
                      <circle
                        r={7}
                        fill="#ffffff"
                        stroke="#6b7280"
                        strokeWidth={1}
                        vectorEffect="non-scaling-stroke"
                      />
                      <line
                        x1={-5}
                        y1={5}
                        x2={5}
                        y2={-5}
                        stroke="#6b7280"
                        strokeWidth={1.5}
                        vectorEffect="non-scaling-stroke"
                      />
                    </g>
                  ) : (
                    <circle
                      cx={x + barWidth / 2}
                      cy={plotBottom + labelHeight + ledHeight / 2}
                      r={6}
                      fill={LED_COLORS[p.state]}
                      stroke={p.state === "N" ? "#9ca3af" : "#065f46"}
                      strokeWidth={p.state === "N" ? 1 : 0.5}
                      vectorEffect="non-scaling-stroke"
                    />
                  )}

                  {/* Native tooltip */}
                  <title>
                    Port {p.port}
                    {p.label ? ` — ${p.label}` : ""}
                    {"\n"}
                    Total: {total}%{"\n"}
                    Unicast/All Tx: {p.usage1}%{"\n"}
                    Non-unicast Rx: {p.usage2}%{"\n"}
                    Errors Rx: {p.usage3}%{"\n"}
                    State: {p.state}
                    {p.speed ? `\nSpeed: ${p.speed}` : ""}
                    {disabled ? "\n(administratively disabled)" : ""}
                  </title>
                </g>
              );
            })}
          </svg>
        </div>

        <UtilizationLegend />
      </div>
    </div>
  );
}

function UtilizationLegend() {
  return (
    <div className="flex flex-col gap-1 rounded border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-700">
      <div className="mb-1 font-semibold uppercase tracking-wide text-neutral-500">
        Legend
      </div>
      <LegendSwatch color={COLOR_USAGE1} label="% Unicast Rx or All Tx" />
      <LegendSwatch color={COLOR_USAGE2} label="% Non-Unicast Pkts Rx" />
      <LegendSwatch color={COLOR_USAGE3} label="% Error Packets Rx" />
      <div className="mt-2 flex items-center gap-1.5">
        <span
          aria-hidden
          className="inline-block h-3 w-3 rounded-full"
          style={{ backgroundColor: LED_COLORS.G }}
        />
        Port Connected
      </div>
      <div className="flex items-center gap-1.5">
        <span
          aria-hidden
          className="inline-block h-3 w-3 rounded-full border border-neutral-400"
          style={{ backgroundColor: LED_COLORS.N }}
        />
        Port Not Connected
      </div>
      <div className="flex items-center gap-1.5">
        <svg width={12} height={12} viewBox="-6 -6 12 12" aria-hidden>
          <circle r={5} fill="#ffffff" stroke="#6b7280" strokeWidth={1} />
          <line x1={-4} y1={4} x2={4} y2={-4} stroke="#6b7280" strokeWidth={1.2} />
        </svg>
        Port Disabled
      </div>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="inline-block h-3 w-3 rounded-sm"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
