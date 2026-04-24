/**
 * Link-test diagnostic card.
 *
 * Same shape as PingCard but hits /link-test. The destination is expected to
 * be a MAC address (either dash-separated like `00-1D-B3-B7-0E-00` or
 * colon-separated like `00:1D:B3:B7:0E:00`).
 */
import { useState, type FormEvent } from "react";
import {
  useLinkTest,
  type LinkTestRequest,
} from "@/api/hooks/useDiagnostics";

const DEFAULT_COUNT = 10;
const DEFAULT_TIMEOUT_S = 5;

export function LinkTestCard() {
  const [destination, setDestination] = useState("");
  const [packetCount, setPacketCount] = useState<number>(DEFAULT_COUNT);
  const linkTest = useLinkTest();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const dest = destination.trim();
    if (!dest) return;
    const body: LinkTestRequest = {
      destination: dest,
      packet_count: Math.max(1, packetCount),
      timeout_s: DEFAULT_TIMEOUT_S,
    };
    linkTest.mutate(body);
  };

  const result = linkTest.data;
  const errorMessage =
    linkTest.error instanceof Error ? linkTest.error.message : null;

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Link test
      </h4>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[16rem]">
          <label
            htmlFor="linktest-destination"
            className="block text-xs font-medium text-neutral-700"
          >
            Destination (MAC address)
          </label>
          <input
            id="linktest-destination"
            type="text"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="e.g. 00-1D-B3-B7-0E-00"
            disabled={linkTest.isPending}
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-neutral-50"
          />
        </div>
        <div className="w-24">
          <label
            htmlFor="linktest-count"
            className="block text-xs font-medium text-neutral-700"
          >
            Count
          </label>
          <input
            id="linktest-count"
            type="number"
            min={1}
            max={100}
            value={packetCount}
            onChange={(e) => setPacketCount(Number(e.target.value) || 1)}
            disabled={linkTest.isPending}
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-neutral-50"
          />
        </div>
        <button
          type="submit"
          disabled={linkTest.isPending || destination.trim().length === 0}
          className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:bg-blue-300"
        >
          {linkTest.isPending ? "Testing…" : "Run link test"}
        </button>
      </form>

      {errorMessage && (
        <div className="mt-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-semibold">Link test failed</p>
          <p className="mt-1 break-all">{errorMessage}</p>
        </div>
      )}

      {result && !errorMessage && (
        <div className="mt-3 rounded-md border border-neutral-200 bg-neutral-50 p-3 text-sm text-neutral-800">
          <p>
            <span className="font-semibold">Results:</span>{" "}
            <span className="font-mono">
              {result.successes}/{result.successes + result.failures}
            </span>{" "}
            successful
            {result.failures > 0 && (
              <span className="ml-2 text-red-700">
                ({result.failures} failed)
              </span>
            )}
          </p>
        </div>
      )}
    </section>
  );
}
