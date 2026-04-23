/**
 * SVG chassis renderer for the HP ProCurve 2810-24G.
 *
 * Layout decision (documented here because the plan left it open):
 *   - 24 copper ports are arranged in 12 columns × 2 rows using the physical
 *     HP layout: odd ports (1, 3, 5 … 23) on the TOP row, even ports
 *     (2, 4, 6 … 24) on the BOTTOM row — i.e. column N contains ports
 *     (2N-1, 2N) from top to bottom. This matches how the faceplate is
 *     silk-screened and what an admin in the server room sees.
 *   - 4 mini-GBIC (SFP) combo slots (ports 25-28) live to the right of the
 *     copper block, stacked as 2 columns × 2 rows with extra horizontal
 *     padding to visually separate the copper and fibre banks.
 *
 * Each port:
 *   - is a rounded neutral-300 rect (the port body)
 *   - has one circular LED whose color reflects link state (see PortLed)
 *   - renders a native <title> so browsers show a hover tooltip without us
 *     having to reinvent a positioning / keyboard-accessibility layer
 *   - has an onClick handler that calls `useNavigate(...)` to route to
 *     /status/ports/:port. We intentionally avoid TanStack Router's <Link>
 *     here because <Link> renders an HTML `<a>` element and nesting `<a>`
 *     inside `<svg>` works inconsistently across browsers; keeping the
 *     click handler imperative keeps the chassis pure SVG.
 *
 * The component is pure and memoizable: it takes `ports` in and returns an
 * <svg>. No data fetching, no Query access, no local state beyond the
 * hovered-port highlight.
 */
import { useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import type { components } from "@/api/schema";
import { PortLed } from "./PortLed";
import { portLedStatus } from "./portLedStatus";

type PortStatus = components["schemas"]["PortStatus"];

// Geometry — tuned so a 600×160 viewBox fits the 24 copper ports (12 cols)
// plus 4 SFP ports on the right with a comfortable margin.
const PORT_WIDTH = 36;
const PORT_HEIGHT = 48;
const COL_GAP = 6;
const ROW_GAP = 8;
const MARGIN_X = 12;
const MARGIN_Y = 14;
const COPPER_COLS = 12;
const SFP_GAP = 18; // extra gap separating the copper bank from the SFP bank

function copperPosition(portNum: number): { x: number; y: number } {
  // portNum 1..24 — column = ceil(portNum/2) - 1 ; row = (portNum-1) % 2
  const col = Math.floor((portNum - 1) / 2);
  const row = (portNum - 1) % 2;
  return {
    x: MARGIN_X + col * (PORT_WIDTH + COL_GAP),
    y: MARGIN_Y + row * (PORT_HEIGHT + ROW_GAP),
  };
}

function sfpPosition(portNum: number): { x: number; y: number } {
  // portNum 25..28 — 2 cols × 2 rows to the right of the copper bank.
  const idx = portNum - 25;
  const col = Math.floor(idx / 2);
  const row = idx % 2;
  const copperRightEdge =
    MARGIN_X + COPPER_COLS * PORT_WIDTH + (COPPER_COLS - 1) * COL_GAP;
  return {
    x: copperRightEdge + SFP_GAP + col * (PORT_WIDTH + COL_GAP),
    y: MARGIN_Y + row * (PORT_HEIGHT + ROW_GAP),
  };
}

function portPosition(portNum: number): { x: number; y: number } {
  return portNum <= 24 ? copperPosition(portNum) : sfpPosition(portNum);
}

// Chassis extents derived from the geometry above.
const CHASSIS_WIDTH =
  MARGIN_X * 2 +
  COPPER_COLS * PORT_WIDTH +
  (COPPER_COLS - 1) * COL_GAP +
  SFP_GAP +
  2 * PORT_WIDTH +
  COL_GAP;
const CHASSIS_HEIGHT = MARGIN_Y * 2 + 2 * PORT_HEIGHT + ROW_GAP;

interface SwitchSvgProps {
  ports: PortStatus[];
}

export function SwitchSvg({ ports }: SwitchSvgProps) {
  const [hoveredPort, setHoveredPort] = useState<number | null>(null);
  const navigate = useNavigate();

  // Index ports by number so we can look up any chassis slot cheaply, and
  // so missing data (24-port data on a 28-slot chassis) renders as a dim
  // empty port rather than blowing up the component.
  const byNum = useMemo(() => {
    const m = new Map<number, PortStatus>();
    for (const p of ports) m.set(p.port, p);
    return m;
  }, [ports]);

  const slots: number[] = [];
  for (let i = 1; i <= 28; i++) slots.push(i);

  return (
    <svg
      viewBox={`0 0 ${CHASSIS_WIDTH} ${CHASSIS_HEIGHT}`}
      xmlns="http://www.w3.org/2000/svg"
      className="w-full max-w-4xl"
      role="img"
      aria-label="Switch port panel"
    >
      {/* Chassis background */}
      <rect
        x={0}
        y={0}
        width={CHASSIS_WIDTH}
        height={CHASSIS_HEIGHT}
        rx={6}
        ry={6}
        fill="#1f2937" // neutral-800 — the darker bezel around the ports
      />

      {slots.map((portNum) => {
        const pos = portPosition(portNum);
        const data = byNum.get(portNum);
        const isSfp = portNum > 24;
        const isHovered = hoveredPort === portNum;

        // Fall back to "disabled"-looking empty body when we don't have data
        // for a slot. This keeps the chassis rendering stable whether the
        // backend reports 24 or 28 ports.
        const ledStatus = data
          ? portLedStatus({
              enabled: data.enabled,
              link_status: data.link_status,
            })
          : "down-disabled";

        const titleParts: string[] = [`Port ${portNum}`];
        if (data) {
          const label = data.port_name?.trim();
          if (label) titleParts.push(`"${label}"`);
          titleParts.push(
            `${data.link_status} / ${data.current_mode || "—"}`,
          );
          if (!data.enabled) titleParts.push("Disabled");
        } else {
          titleParts.push("(no data)");
        }
        const title = titleParts.join(" • ");

        const go = () =>
          navigate({
            to: "/status/ports/$port",
            params: { port: String(portNum) },
          });

        return (
          <g
            key={portNum}
            role="button"
            tabIndex={0}
            onClick={go}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                go();
              }
            }}
            onMouseEnter={() => setHoveredPort(portNum)}
            onMouseLeave={() =>
              setHoveredPort((h) => (h === portNum ? null : h))
            }
            style={{ cursor: "pointer", outline: "none" }}
            aria-label={title}
          >
            <title>{title}</title>
            {/* Port body */}
            <rect
              x={pos.x}
              y={pos.y}
              width={PORT_WIDTH}
              height={PORT_HEIGHT}
              rx={3}
              ry={3}
              fill={isSfp ? "#52525b" : "#d4d4d8"}
              stroke={isHovered ? "#3b82f6" : "#09090b"}
              strokeWidth={isHovered ? 2 : 1}
            />
            {/* Port number label */}
            <text
              x={pos.x + PORT_WIDTH / 2}
              y={pos.y + PORT_HEIGHT - 6}
              textAnchor="middle"
              fontSize={9}
              fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
              fill={isSfp ? "#f4f4f5" : "#27272a"}
            >
              {portNum}
            </text>
            {/* RJ45 / SFP faceplate detail — purely decorative */}
            <rect
              x={pos.x + 4}
              y={pos.y + 6}
              width={PORT_WIDTH - 8}
              height={PORT_HEIGHT - 24}
              rx={2}
              ry={2}
              fill={isSfp ? "#27272a" : "#71717a"}
            />
            {/* LED */}
            <PortLed
              cx={pos.x + PORT_WIDTH / 2}
              cy={pos.y + 3.5}
              status={ledStatus}
            />
          </g>
        );
      })}
    </svg>
  );
}
