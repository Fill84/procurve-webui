/**
 * MonitorCard — port-mirroring enable + destination / source picker.
 *
 * Port mirroring copies all traffic from a set of source ports onto a
 * single destination port (for a sniffer). The switch encodes the source
 * set as a bitmask (`portCopySourceMask`); bit N = port N+1 on this
 * firmware. Not lockout-risky — a copy of traffic won't sever the
 * management session.
 *
 * When monitoring is disabled we send only `enabled: false`; when
 * enabling, both `dest_port` and `source_mask` are required (the
 * backend model validates that).
 *
 * We derive the candidate source-port list from the bob-ports read
 * (every port on the device minus the selected destination). That read
 * is cheap and the Configuration tab already loads it elsewhere, so the
 * extra query is free once it's cached.
 */
import { useEffect, useState } from "react";
import {
  useBobPorts,
  useMonitor,
  useSetMonitor,
  type SetMonitorRequest,
} from "@/api/hooks/useConfiguration";

function maskToPorts(mask: number): number[] {
  const out: number[] = [];
  for (let p = 1; p <= 64; p++) {
    if (mask & (1 << (p - 1))) out.push(p);
  }
  return out;
}

function portsToMask(ports: number[]): number {
  let mask = 0;
  for (const p of ports) mask |= 1 << (p - 1);
  return mask;
}

export function MonitorCard() {
  const query = useMonitor();
  const bob = useBobPorts();
  const mutation = useSetMonitor();

  const [enabled, setEnabled] = useState(false);
  const [destPort, setDestPort] = useState<number | null>(null);
  const [sourcePorts, setSourcePorts] = useState<Set<number>>(new Set());
  const [lastResult, setLastResult] = useState<string | null>(null);

  useEffect(() => {
    if (query.data) {
      setEnabled(query.data.enabled);
      setDestPort(
        query.data.selected_dest_port ??
          (query.data.candidate_dest_ports?.[0] ?? null),
      );
      // Monitor read doesn't expose the current source mask — leave empty
      // and let the operator pick sources when enabling.
      setSourcePorts(new Set());
    }
  }, [query.data]);

  const destCandidates = query.data?.candidate_dest_ports ?? [];
  const allPorts = (bob.data?.ports ?? []).map((p) => p.port);
  // Source ports: everything minus the selected destination.
  const sourceCandidates = allPorts.filter((p) => p !== destPort);

  const toggleSource = (port: number) => {
    setSourcePorts((prev) => {
      const next = new Set(prev);
      if (next.has(port)) next.delete(port);
      else next.add(port);
      return next;
    });
  };

  const handleSave = () => {
    setLastResult(null);
    mutation.reset();
    const request: SetMonitorRequest = enabled
      ? {
          enabled: true,
          dest_port: destPort,
          source_mask: portsToMask(Array.from(sourcePorts)),
        }
      : { enabled: false };
    mutation.mutate(
      { request },
      {
        onSuccess: (data) => {
          setLastResult(
            data.ok
              ? "Port mirroring saved."
              : "Save accepted without confirmation.",
          );
          // Reload the server view so the card shows what actually stuck.
          void query.refetch();
        },
      },
    );
  };

  const errorMessage =
    mutation.error instanceof Error ? mutation.error.message : null;

  const saveDisabled =
    mutation.isPending ||
    (enabled && (destPort === null || sourcePorts.size === 0));

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Port mirroring
        </h4>
        {(query.isLoading || bob.isLoading) && (
          <span className="text-xs text-neutral-500">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-medium">Failed to load monitor config</p>
          <p className="mt-1 break-all">{query.error.message}</p>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="mt-2 rounded-md border border-red-400 bg-white px-3 py-1.5 text-sm font-medium text-red-900 hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      )}

      {query.data && (
        <>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="font-medium text-neutral-800">
              Enable port mirroring
            </span>
          </label>

          {enabled && (
            <div className="mt-3 grid gap-3">
              <div>
                <label
                  htmlFor="mon-dest"
                  className="block text-xs font-medium text-neutral-700"
                >
                  Destination port (sniffer)
                </label>
                <select
                  id="mon-dest"
                  value={destPort ?? ""}
                  onChange={(e) =>
                    setDestPort(
                      e.target.value === "" ? null : Number(e.target.value),
                    )
                  }
                  className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">— select —</option>
                  {destCandidates.map((p) => (
                    <option key={p} value={p}>
                      Port {p}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <span className="block text-xs font-medium text-neutral-700">
                  Source ports (mirrored to the destination)
                </span>
                {sourceCandidates.length === 0 ? (
                  <p className="mt-1 text-xs text-neutral-500">
                    No candidate ports (bob-ports list not loaded).
                  </p>
                ) : (
                  <div className="mt-1 grid grid-cols-4 gap-2 sm:grid-cols-6 md:grid-cols-8">
                    {sourceCandidates.map((p) => (
                      <label
                        key={p}
                        className="flex items-center gap-1 text-xs"
                      >
                        <input
                          type="checkbox"
                          checked={sourcePorts.has(p)}
                          onChange={() => toggleSource(p)}
                          className="h-3.5 w-3.5 rounded border-neutral-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="font-mono text-neutral-700">
                          {p}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saveDisabled}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {mutation.isPending ? "Saving…" : "Save"}
            </button>
            {lastResult && (
              <span className="text-sm italic text-neutral-700">
                {lastResult}
              </span>
            )}
          </div>

          {errorMessage && (
            <div className="mt-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              <p className="font-semibold">Save failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}

// Export for testability (keeps tree-shaking happy if a future unit test
// imports the pure helpers).
export { maskToPorts, portsToMask };
