/**
 * Small, dependency-free formatters used by read-only display pages.
 *
 * Kept intentionally tiny — no i18n, no pluralisation libraries. The switch is
 * single-tenant and English-only in Phase 2, so verifying output visually in
 * the browser is cheaper than adding a unit-test toolchain that doesn't yet
 * exist on the frontend.
 */

/**
 * Format a ProCurve uptime value (hundredths of a second since boot) as a
 * human-readable string, e.g. "3 days, 14:22:09" or "00:05:12".
 */
export function formatUptime(centiseconds: number): string {
  const totalSeconds = Math.floor(centiseconds / 100);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const hhmmss = [hours, minutes, seconds]
    .map((n) => String(n).padStart(2, "0"))
    .join(":");
  return days > 0 ? `${days} day${days === 1 ? "" : "s"}, ${hhmmss}` : hhmmss;
}

/**
 * Format a byte count in binary units (KB/MB/GB/TB = 1024-based) with one
 * decimal place, matching how the ProCurve applet reports memory.
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let i = -1;
  let value = bytes;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}
