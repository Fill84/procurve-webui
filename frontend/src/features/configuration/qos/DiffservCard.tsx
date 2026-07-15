/**
 * DiffservCard — inbound DSCP policy table (``/cgi/diffserv_get`` + ``_set``).
 *
 * Each row maps an inbound codepoint to a DSCP value the switch rewrites
 * to on ingress. Like the DSCP table, each edit is one PUT.
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useQosDiffserv,
  useSetQosDiffserv,
  type DiffservEntry,
} from "@/api/hooks/useConfiguration";

export function DiffservCard() {
  const query = useQosDiffserv();
  const mutation = useSetQosDiffserv();

  const [editing, setEditing] = useState<number | null>(null);
  const [dscp, setDscp] = useState<number>(0);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const rows = query.data?.rows ?? [];

  const beginEdit = (row: DiffservEntry) => {
    setEditing(row.row_index);
    setDscp(parseInt(row.inbound_codepoint, 2));
    setLastResult(null);
    mutation.reset();
  };

  const submit = () => {
    if (editing === null) return;
    mutation.mutate(
      { request: { row_index: editing, dscp } },
      {
        onSuccess: () => {
          setLastResult(`Saved row ${editing}.`);
          setEditing(null);
          void query.refetch();
        },
      },
    );
  };

  const errorMessage =
    apiErrorMessage(mutation.error);

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          DiffServ — inbound DSCP policy
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <ErrorBanner className="mb-3">
          <p className="font-medium">Failed to load DiffServ table</p>
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
          <div className="max-h-96 overflow-auto rounded border border-border">
            <table className="min-w-full text-sm">
              <thead className="sticky top-0 bg-muted text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Row</th>
                  <th className="px-3 py-2 text-left">Codepoint</th>
                  <th className="px-3 py-2 text-left">DSCP policy</th>
                  <th className="px-3 py-2 text-left">Priority</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r) => {
                  const isEditing = editing === r.row_index;
                  return (
                    <tr
                      key={r.row_index}
                      className={isEditing ? "bg-amber-50 dark:bg-amber-950/40" : undefined}
                    >
                      <td className="px-3 py-1.5 font-mono">{r.row_index}</td>
                      <td className="px-3 py-1.5 font-mono">
                        {r.inbound_codepoint}
                      </td>
                      <td className="px-3 py-1.5">
                        {isEditing ? (
                          <input
                            type="number"
                            min={0}
                            max={63}
                            value={dscp}
                            onChange={(e) => setDscp(Number(e.target.value))}
                            className="w-20 rounded-md border border-border px-2 py-0.5 text-xs"
                          />
                        ) : (
                          r.dscp_policy
                        )}
                      </td>
                      <td className="px-3 py-1.5">{r.priority_label}</td>
                      <td className="px-3 py-1.5 text-right">
                        {isEditing ? (
                          <div className="flex justify-end gap-2">
                            <button
                              type="button"
                              onClick={submit}
                              disabled={mutation.isPending}
                              className="rounded bg-blue-600 px-2 py-0.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:bg-blue-300"
                            >
                              {mutation.isPending ? "Saving…" : "Save"}
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditing(null)}
                              disabled={mutation.isPending}
                              className="text-xs text-muted-foreground hover:underline"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => beginEdit(r)}
                            disabled={mutation.isPending}
                            className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                          >
                            Edit
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {lastResult && (
            <p className="mt-3 text-sm italic text-foreground">
              {lastResult}
            </p>
          )}

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
