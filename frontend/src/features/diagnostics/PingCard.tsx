/**
 * Ping diagnostic card.
 *
 * User types an IPv4 or hostname plus an optional packet count, clicks
 * "Run ping", and we surface the switch's Successes/Failures counters.
 * The "Run" button is disabled while the mutation is in-flight.
 */
import { apiErrorMessage } from "@/api/client";
import { useState, type FormEvent } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { usePing, type PingRequest } from "@/api/hooks/useDiagnostics";

const DEFAULT_COUNT = 10;
const DEFAULT_TIMEOUT_S = 5;

export function PingCard() {
  const [destination, setDestination] = useState("");
  const [packetCount, setPacketCount] = useState<number>(DEFAULT_COUNT);
  const ping = usePing();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const dest = destination.trim();
    if (!dest) return;
    const body: PingRequest = {
      destination: dest,
      packet_count: Math.max(1, packetCount),
      timeout_s: DEFAULT_TIMEOUT_S,
    };
    ping.mutate(body);
  };

  const result = ping.data;
  const errorMessage =
    apiErrorMessage(ping.error);

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Ping
      </h4>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[16rem]">
          <label
            htmlFor="ping-destination"
            className="block text-xs font-medium text-foreground"
          >
            Destination (IP or hostname)
          </label>
          <input
            id="ping-destination"
            type="text"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="e.g. 8.8.8.8"
            disabled={ping.isPending}
            className="mt-1 w-full rounded-md border border-border px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-muted"
          />
        </div>
        <div className="w-24">
          <label
            htmlFor="ping-count"
            className="block text-xs font-medium text-foreground"
          >
            Count
          </label>
          <input
            id="ping-count"
            type="number"
            min={1}
            max={100}
            value={packetCount}
            onChange={(e) => setPacketCount(Number(e.target.value) || 1)}
            disabled={ping.isPending}
            className="mt-1 w-full rounded-md border border-border px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-muted"
          />
        </div>
        <button
          type="submit"
          disabled={ping.isPending || destination.trim().length === 0}
          className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:bg-blue-300"
        >
          {ping.isPending ? "Pinging…" : "Run ping"}
        </button>
      </form>

      {errorMessage && (
        <ErrorBanner title="Ping failed" className="mt-3">
          {errorMessage}
        </ErrorBanner>
      )}

      {result && !errorMessage && (
        <div className="mt-3 rounded-md border border-border bg-muted p-3 text-sm text-foreground">
          <p>
            <span className="font-semibold">Results:</span>{" "}
            <span className="font-mono">
              {result.successes}/{result.successes + result.failures}
            </span>{" "}
            successful
            {result.failures > 0 && (
              <span className="ml-2 text-red-700 dark:text-red-300">
                ({result.failures} failed)
              </span>
            )}
          </p>
        </div>
      )}
    </section>
  );
}
