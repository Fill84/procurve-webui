import { describe, expect, it } from "vitest";
import {
  entryCovers,
  isContiguousNetmask,
  isValidIpv4,
  parseIpv4,
} from "./ipv4";

describe("parseIpv4 / isValidIpv4", () => {
  it("parses a dotted quad", () => {
    expect(parseIpv4("192.168.1.10")).toBe(
      192 * 256 ** 3 + 168 * 256 ** 2 + 256 + 10,
    );
  });

  it("rejects malformed input", () => {
    for (const bad of [
      "",
      "192.168.1",
      "192.168.1.10.5",
      "999.1.1.1",
      "1.2.3.256",
      "a.b.c.d",
      "192.168.1.10/24",
      "192.168.1.-1",
    ]) {
      expect(isValidIpv4(bad), bad).toBe(false);
    }
  });

  it("accepts surrounding whitespace", () => {
    expect(isValidIpv4(" 10.0.0.1 ")).toBe(true);
  });
});

describe("isContiguousNetmask", () => {
  it("accepts conventional masks", () => {
    for (const mask of [
      "255.255.255.255",
      "255.255.255.0",
      "255.255.254.0",
      "255.0.0.0",
      "0.0.0.0",
    ]) {
      expect(isContiguousNetmask(mask), mask).toBe(true);
    }
  });

  it("flags non-contiguous bit patterns", () => {
    expect(isContiguousNetmask("255.0.255.0")).toBe(false);
    expect(isContiguousNetmask("255.255.255.1")).toBe(false);
  });
});

describe("entryCovers", () => {
  it("matches a host entry exactly", () => {
    expect(entryCovers("192.168.1.50", "255.255.255.255", "192.168.1.50")).toBe(
      true,
    );
    expect(entryCovers("192.168.1.50", "255.255.255.255", "192.168.1.51")).toBe(
      false,
    );
  });

  it("matches a subnet entry", () => {
    expect(entryCovers("192.168.1.0", "255.255.255.0", "192.168.1.99")).toBe(
      true,
    );
    expect(entryCovers("192.168.1.0", "255.255.255.0", "192.168.2.99")).toBe(
      false,
    );
  });

  it("is false on unparseable input (advisory-only semantics)", () => {
    expect(entryCovers("garbage", "255.255.255.0", "192.168.1.1")).toBe(false);
  });
});
