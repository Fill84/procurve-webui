/**
 * Mapping helper: translate a raw `PortStatus` row (enabled + link_status)
 * into the stricter three-state LED enum used by the chassis renderer and
 * any future legend / detail component.
 *
 * Lives in its own module so PortLed.tsx can stay a pure-component file
 * (react-refresh requires that).
 */

export type PortLedStatus = "up" | "down-enabled" | "down-disabled";

export function portLedStatus(args: {
  enabled: boolean;
  link_status: "Up" | "Down";
}): PortLedStatus {
  if (!args.enabled) return "down-disabled";
  return args.link_status === "Up" ? "up" : "down-enabled";
}
