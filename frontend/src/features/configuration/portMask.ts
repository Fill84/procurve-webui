/**
 * Port bitmask helpers for the monitor (port-mirroring) CGI, split out of
 * MonitorCard.tsx so that file exports only its component (Fast Refresh
 * requirement) and the pure helpers stay unit-testable.
 *
 * NOTE: JS bitwise ops are 32-bit — safe here because the 2810-24G tops out
 * at 26 ports (24 + 2 uplinks); do not reuse for hypothetical >31-port masks.
 * The scan deliberately stops at 32: `1 << 32` wraps to `1 << 0`, so probing
 * bits 33-64 (as an earlier version did) reported phantom duplicate ports
 * (port 33 aliasing port 1, etc.).
 */
export function maskToPorts(mask: number): number[] {
  const out: number[] = [];
  for (let p = 1; p <= 32; p++) {
    if (mask & (1 << (p - 1))) out.push(p);
  }
  return out;
}

export function portsToMask(ports: number[]): number {
  let mask = 0;
  for (const p of ports) mask |= 1 << (p - 1);
  return mask;
}
