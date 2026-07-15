/**
 * IPv4 helpers for the authorized-managers whitelist validation (audit L7).
 *
 * The whitelist semantics on the 2810: an entry covers a client when
 * `(client & mask) === (entry_ip & mask)`. An EMPTY whitelist means
 * "no restriction" — everyone is allowed.
 */

/** Parse a dotted-quad IPv4 literal into a uint32, or null when invalid. */
export function parseIpv4(s: string): number | null {
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(s.trim());
  if (!m) return null;
  let value = 0;
  for (let i = 1; i <= 4; i++) {
    const octet = Number(m[i]);
    if (octet > 255) return null;
    value = value * 256 + octet;
  }
  return value;
}

export function isValidIpv4(s: string): boolean {
  return parseIpv4(s) !== null;
}

/**
 * True when `s` is a valid dotted-quad AND its bits are contiguous
 * ones-then-zeros (a conventional netmask). The firmware accepts
 * non-contiguous masks, so callers should treat a `false` from this (on an
 * otherwise valid quad) as a warning, not a hard error.
 */
export function isContiguousNetmask(s: string): boolean {
  const v = parseIpv4(s);
  if (v === null) return false;
  // A contiguous mask inverted is 2^n - 1; adding 1 yields a power of two.
  const inverted = (~v >>> 0) + 1;
  return (inverted & (inverted - 1)) === 0;
}

/** Whether the whitelist entry (ip, mask) covers `client`. */
export function entryCovers(
  entryIp: string,
  mask: string,
  clientIp: string,
): boolean {
  const e = parseIpv4(entryIp);
  const m = parseIpv4(mask);
  const c = parseIpv4(clientIp);
  if (e === null || m === null || c === null) return false;
  return ((e & m) >>> 0) === ((c & m) >>> 0);
}
