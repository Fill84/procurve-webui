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
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { useServerSync } from "@/lib/useServerSync";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useBobPorts,
  useMonitor,
  useSetMonitor,
  type SetMonitorRequest,
} from "@/api/hooks/useConfiguration";
import { portsToMask } from "./portMask";

export function MonitorCard() {
  const query = useMonitor();
  const bob = useBobPorts();
  const mutation = useSetMonitor();

  const [enabled, setEnabled] = useState(false);
  const [destPort, setDestPort] = useState<number | null>(null);
  const [sourcePorts, setSourcePorts] = useState<Set<number>>(new Set());
  const [lastResult, setLastResult] = useState<string | null>(null);

  useServerSync(query.data, (data) => {
    setEnabled(data.enabled);
    setDestPort(
      data.selected_dest_port ?? (data.candidate_dest_ports?.[0] ?? null),
    );
    // Monitor read doesn't expose the current source mask — leave empty
    // and let the operator pick sources when enabling.
    setSourcePorts(new Set());
  });

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
    apiErrorMessage(mutation.error);

  const saveDisabled =
    mutation.isPending ||
    (enabled && (destPort === null || sourcePorts.size === 0));

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Port mirroring
        </h4>
        {(query.isLoading || bob.isLoading) && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <ErrorBanner>
          <p className="font-medium">Failed to load monitor config</p>
          <p className="mt-1 break-all">{query.error.message}</p>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="mt-2 rounded-md border border-red-400 dark:border-red-900 bg-card px-3 py-1.5 text-sm font-medium text-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
          >
            Retry
          </button>
        </ErrorBanner>
      )}

      {query.data && (
        <>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-border text-blue-600 focus:ring-blue-500"
            />
            <span className="font-medium text-foreground">
              Enable port mirroring
            </span>
          </label>

          {enabled && (
            <div className="mt-3 grid gap-3">
              <div>
                <label
                  htmlFor="mon-dest"
                  className="block text-xs font-medium text-foreground"
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
                  className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
                <span className="block text-xs font-medium text-foreground">
                  Source ports (mirrored to the destination)
                </span>
                {sourceCandidates.length === 0 ? (
                  <p className="mt-1 text-xs text-muted-foreground">
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
                          className="h-3.5 w-3.5 rounded border-border text-blue-600 focus:ring-blue-500"
                        />
                        <span className="font-mono text-foreground">
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
              <span className="text-sm italic text-foreground">
                {lastResult}
              </span>
            )}
          </div>

          {errorMessage && (
            <ErrorBanner title="Save failed" className="mt-3">
              {errorMessage}
            </ErrorBanner>
          )}
        </>
      )}
    </section>
  );
}
