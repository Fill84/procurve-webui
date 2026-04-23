/**
 * Small SVG LED indicator used inside SwitchSvg.
 *
 * Color semantics, intentionally stricter than the applet:
 *   - up             : link is Up (green, gently pulsing to imply "live traffic")
 *   - down-enabled   : port is enabled but link is Down (amber — the only state
 *                      likely to indicate an actual problem)
 *   - down-disabled  : port is administratively Disabled (gray — operator intent)
 *
 * Rendered as a bare <circle> so it composes naturally into the parent <svg>
 * chassis without needing a wrapper <g>. The pulse for "up" is a looping
 * opacity <animate>; CSS animations would require a class on an inline SVG
 * and we prefer to keep the chassis style-free.
 *
 * The `portLedStatus` helper that maps a raw PortStatus row to one of these
 * three values lives in ./portLedStatus.ts so this file exports only the
 * component (react-refresh constraint).
 */
import type { PortLedStatus } from "./portLedStatus";

interface PortLedProps {
  cx: number;
  cy: number;
  r?: number;
  status: PortLedStatus;
}

const COLOR: Record<PortLedStatus, string> = {
  "up": "#22c55e",            // green-500
  "down-enabled": "#f59e0b",  // amber-500
  "down-disabled": "#a3a3a3", // neutral-400
};

export function PortLed({ cx, cy, r = 3, status }: PortLedProps) {
  const fill = COLOR[status];
  return (
    <circle cx={cx} cy={cy} r={r} fill={fill} stroke="#0a0a0a" strokeWidth={0.5}>
      {status === "up" && (
        <animate
          attributeName="opacity"
          values="1;0.55;1"
          dur="1.8s"
          repeatCount="indefinite"
        />
      )}
    </circle>
  );
}
