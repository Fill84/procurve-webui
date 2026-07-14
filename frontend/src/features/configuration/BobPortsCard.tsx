/**
 * BobPortsCard — device-view admin-status toggle (per port).
 *
 * Backend shape: `GET /bob-ports` returns the chassis + per-port
 * [port, kind, label, link, enabled, mode?, poe?]. The matching write
 * (`PUT /bob-ports`) takes `{enable: bool, ports: [int, ...]}`:
 * all selected ports are set to the same admin state in a single call.
 *
 * UX
 * --
 *   * One row per port with an admin-status checkbox.
 *   * [Enable all] / [Disable all] buttons as convenience shortcuts —
 *     they *stage* changes locally, they don't fire the write until
 *     the operator clicks [Apply].
 *   * The pending/dirty state is derived by diffing the staged state
 *     against what the server reported.
 *   * We split into two PUTs (one for enables, one for disables) when
 *     the staged diff spans both directions, because `set_bobports`
 *     only accepts one direction at a time.
 *
 * Not lockout-risky in the sense of the routing path; the pre-write
 * autobackup on the backend is the rollback mechanism. If the operator
 * disables their own uplink, they would need to recover via the
 * backend's local backup restore — same failure mode as the per-port
 * config endpoint.
 */
import { useEffect, useMemo, useState } from "react";
import {
  useBobPorts,
  useSetBobPorts,
  type BobPort,
} from "@/api/hooks/useConfiguration";

export function BobPortsCard() {
  const query = useBobPorts();
  const mutation = useSetBobPorts();

  // Local staged state: port -> desired enabled flag. Seeded from server.
  const [staged, setStaged] = useState<Record<number, boolean>>({});
  const [lastResult, setLastResult] = useState<string | null>(null);

  useEffect(() => {
    if (query.data) {
      const next: Record<number, boolean> = {};
      for (const p of query.data.ports ?? []) {
        next[p.port] = p.enabled;
      }
      setStaged(next);
    }
  }, [query.data]);

  const serverPorts = query.data?.ports ?? [];

  const { toEnable, toDisable } = useMemo(() => {
    const en: number[] = [];
    const dis: number[] = [];
    for (const p of serverPorts) {
      const want = staged[p.port];
      if (want === undefined) continue;
      if (want !== p.enabled) {
        if (want) en.push(p.port);
        else dis.push(p.port);
      }
    }
    return { toEnable: en, toDisable: dis };
  }, [serverPorts, staged]);

  const dirty = toEnable.length > 0 || toDisable.length > 0;

  const toggleOne = (port: number) => {
    setStaged((prev) => ({ ...prev, [port]: !prev[port] }));
  };

  const stageAll = (enable: boolean) => {
    const next: Record<number, boolean> = {};
    for (const p of serverPorts) next[p.port] = enable;
    setStaged(next);
  };

  const revert = () => {
    const next: Record<number, boolean> = {};
    for (const p of serverPorts) next[p.port] = p.enabled;
    setStaged(next);
    setLastResult(null);
    mutation.reset();
  };

  const handleApply = async () => {
    setLastResult(null);
    mutation.reset();
    try {
      // Fire one PUT per direction that has queued changes.
      if (toEnable.length > 0) {
        await mutation.mutateAsync({
          request: { enable: true, ports: toEnable },
        });
      }
      if (toDisable.length > 0) {
        await mutation.mutateAsync({
          request: { enable: false, ports: toDisable },
        });
      }
      const parts: string[] = [];
      if (toEnable.length > 0)
        parts.push(`enabled ${toEnable.length} port(s)`);
      if (toDisable.length > 0)
        parts.push(`disabled ${toDisable.length} port(s)`);
      setLastResult(parts.length > 0 ? `Applied: ${parts.join(", ")}.` : null);
      void query.refetch();
    } catch {
      // mutation.error is rendered below; no extra handling needed.
    }
  };

  const errorMessage =
    mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Device view — admin status
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <div className="mb-3 rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
          <p className="font-medium">Failed to load port list</p>
          <p className="mt-1 break-all">{query.error.message}</p>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="mt-2 rounded-md border border-red-400 dark:border-red-900 bg-card px-3 py-1.5 text-sm font-medium text-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
          >
            Retry
          </button>
        </div>
      )}

      {query.data && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => stageAll(true)}
              className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
            >
              Enable all
            </button>
            <button
              type="button"
              onClick={() => stageAll(false)}
              className="rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
            >
              Disable all
            </button>
            <span className="ml-2 text-xs text-muted-foreground">
              {serverPorts.length} port(s) · {dirty ? "pending changes" : "no pending changes"}
            </span>
          </div>

          <div className="overflow-x-auto rounded border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Port</th>
                  <th className="px-3 py-2 text-left">Label</th>
                  <th className="px-3 py-2 text-left">Kind</th>
                  <th className="px-3 py-2 text-left">Link</th>
                  <th className="px-3 py-2 text-left">Admin</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {serverPorts.map((p: BobPort) => {
                  const want = staged[p.port] ?? p.enabled;
                  const changed = want !== p.enabled;
                  return (
                    <tr
                      key={p.port}
                      className={changed ? "bg-amber-50 dark:bg-amber-950/40" : undefined}
                    >
                      <td className="px-3 py-1.5 font-mono">{p.port}</td>
                      <td className="px-3 py-1.5 text-foreground">
                        {p.label || "—"}
                      </td>
                      <td className="px-3 py-1.5 text-muted-foreground">
                        {p.kind}
                      </td>
                      <td className="px-3 py-1.5">
                        <span
                          className={
                            p.link
                              ? "rounded bg-green-100 dark:bg-green-900/40 px-1.5 py-0.5 text-xs text-green-800 dark:text-green-300"
                              : "rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                          }
                        >
                          {p.link ? "up" : "down"}
                        </span>
                      </td>
                      <td className="px-3 py-1.5">
                        <label className="flex items-center gap-2 text-xs">
                          <input
                            type="checkbox"
                            checked={want}
                            onChange={() => toggleOne(p.port)}
                            className="h-4 w-4 rounded border-border text-blue-600 focus:ring-blue-500"
                          />
                          <span>{want ? "Enabled" : "Disabled"}</span>
                        </label>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                void handleApply();
              }}
              disabled={!dirty || mutation.isPending}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {mutation.isPending ? "Applying…" : "Apply"}
            </button>
            {dirty && !mutation.isPending && (
              <button
                type="button"
                onClick={revert}
                className="text-sm text-muted-foreground hover:text-foreground hover:underline"
              >
                Revert
              </button>
            )}
            {lastResult && (
              <span className="text-sm italic text-foreground">
                {lastResult}
              </span>
            )}
          </div>

          {errorMessage && (
            <div className="mt-3 rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
              <p className="font-semibold">Apply failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
