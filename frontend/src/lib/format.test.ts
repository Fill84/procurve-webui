import { describe, expect, it } from "vitest";
import { formatUptime } from "./format";
import { maskToPorts, portsToMask } from "@/features/configuration/portMask";
import { portLedStatus } from "@/components/switch-panel/portLedStatus";

describe("formatUptime", () => {
  it("formats sub-day uptimes as HH:MM:SS", () => {
    expect(formatUptime(0)).toMatch(/00:00:00/);
    // 5 min 12 s = 31200 centiseconds
    expect(formatUptime(31_200)).toMatch(/00:05:12/);
  });

  it("includes days once uptime exceeds 24h", () => {
    // 3 days, 14:22:09
    const cs = ((3 * 86400 + 14 * 3600 + 22 * 60 + 9) * 100);
    const out = formatUptime(cs);
    expect(out).toContain("3 day");
    expect(out).toContain("14:22:09");
  });

  it("truncates centisecond remainders instead of rounding up", () => {
    expect(formatUptime(199)).toMatch(/00:00:01/);
  });
});

describe("port bitmask helpers", () => {
  it("round-trips all 26 possible ports", () => {
    const all = Array.from({ length: 26 }, (_, i) => i + 1);
    expect(maskToPorts(portsToMask(all))).toEqual(all);
  });

  it("round-trips sparse selections", () => {
    const picks = [1, 5, 24];
    expect(maskToPorts(portsToMask(picks))).toEqual(picks);
  });

  it("maps an empty selection to mask 0 and back", () => {
    expect(portsToMask([])).toBe(0);
    expect(maskToPorts(0)).toEqual([]);
  });

  it("sets the expected bit per port (port 1 = LSB)", () => {
    expect(portsToMask([1])).toBe(1);
    expect(portsToMask([2])).toBe(2);
    expect(portsToMask([3])).toBe(4);
  });
});

describe("portLedStatus", () => {
  it("prioritizes the disabled state over link state", () => {
    expect(portLedStatus({ enabled: false, link_status: "Up" })).toBe(
      "down-disabled",
    );
    expect(portLedStatus({ enabled: false, link_status: "Down" })).toBe(
      "down-disabled",
    );
  });

  it("distinguishes link-up from enabled-but-down", () => {
    expect(portLedStatus({ enabled: true, link_status: "Up" })).toBe("up");
    expect(portLedStatus({ enabled: true, link_status: "Down" })).toBe(
      "down-enabled",
    );
  });
});
