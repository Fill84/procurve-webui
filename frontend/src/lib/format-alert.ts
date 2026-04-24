/**
 * Render a human timestamp for an alert event.
 *
 * `ts_centiseconds` on this firmware is **sysUpTime** — centiseconds since
 * the switch last booted, not a wall-clock value. See
 * research/protocol/status/get_alert_log.md → "Timestamps are centiseconds,
 * not ms. Matches the Identity-tab uptime convention."
 *
 * To turn that into something a human recognises we anchor it to the
 * browser's wall clock at the moment the identity page was last read:
 *
 *     event_wall_ms = now_ms - (current_uptime_centi - alert_uptime_centi) * 10
 *
 * The `current_uptime_centi` comes from `useIdentity().uptime_centiseconds`,
 * and the drift between that read and "now" is small enough (tens of
 * seconds at most — useIdentity polls on mount) that the result is accurate
 * to the second.
 *
 * When identity hasn't loaded yet we render a relative form ("uptime+Xs")
 * so the caller still gets something sortable and self-consistent.
 */
export function formatAlertTimestamp(
  tsCenti: number,
  currentUptimeCenti: number | undefined,
): string {
  if (currentUptimeCenti === undefined) {
    return `uptime+${Math.floor(tsCenti / 100)}s`;
  }
  const ageMs = Math.max(0, (currentUptimeCenti - tsCenti) * 10);
  const wallMs = Date.now() - ageMs;
  const d = new Date(wallMs);
  if (!Number.isFinite(d.getTime())) return `t=${tsCenti}`;

  const absolute = d
    .toISOString()
    .replace("T", " ")
    .replace(/\.\d+Z$/, "Z");
  return `${absolute} (${formatRelative(ageMs)})`;
}

function formatRelative(ageMs: number): string {
  const s = Math.floor(ageMs / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h${m % 60 ? ` ${m % 60}m` : ""} ago`;
  const days = Math.floor(h / 24);
  return `${days}d ${h % 24}h ago`;
}
