/**
 * DscpTableCard — 64-row DSCP → 802.1p priority map.
 *
 * The backend write is row-at-a-time (``PUT /qos/dscp`` takes a single
 * ``(row_index, priority_8021p)`` pair). Editing the whole table would
 * require 64 separate writes; the UI surfaces this by letting the operator
 * pick one row, adjust its priority, and apply — each click = one PUT.
 *
 * ``row_index = codepoint + 1`` (1..64); ``priority_8021p = 255`` means
 * "No Override".
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useQosDscp,
  useSetQosDscp,
  type DscpPolicy,
} from "@/api/hooks/useConfiguration";

const PRIORITY_OPTIONS = [
  { value: 255, label: "No Override" },
  { value: 0, label: "0 (lowest)" },
  { value: 1, label: "1" },
  { value: 2, label: "2" },
  { value: 3, label: "3" },
  { value: 4, label: "4" },
  { value: 5, label: "5" },
  { value: 6, label: "6" },
  { value: 7, label: "7 (highest)" },
];

export function DscpTableCard() {
  const query = useQosDscp();
  const mutation = useSetQosDscp();

  const [editing, setEditing] = useState<number | null>(null);
  const [priority, setPriority] = useState<number>(255);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const rows = query.data?.rows ?? [];

  const beginEdit = (row: DscpPolicy) => {
    setEditing(row.row_index);
    // Pre-select the current priority if it parses to a digit.
    const n = Number(row.priority_label);
    setPriority(
      Number.isInteger(n) && n >= 0 && n <= 7 ? n : 255,
    );
    setLastResult(null);
    mutation.reset();
  };

  const submit = () => {
    if (editing === null) return;
    mutation.mutate(
      { request: { row_index: editing, priority_8021p: priority } },
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
          DSCP → 802.1p map
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      <p className="mb-3 text-xs text-muted-foreground">
        64 rows. Edit one at a time — each row is a separate write and a
        separate autobackup on the backend.
      </p>

      {query.error instanceof Error && (
        <ErrorBanner className="mb-3">
          <p className="font-medium">Failed to load DSCP table</p>
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
                  <th className="px-3 py-2 text-left">DSCP</th>
                  <th className="px-3 py-2 text-left">Priority</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r) => {
                  const dscp = parseInt(r.codepoint, 2);
                  const isEditing = editing === r.row_index;
                  return (
                    <tr
                      key={r.row_index}
                      className={isEditing ? "bg-amber-50 dark:bg-amber-950/40" : undefined}
                    >
                      <td className="px-3 py-1.5 font-mono">{r.row_index}</td>
                      <td className="px-3 py-1.5 font-mono">{r.codepoint}</td>
                      <td className="px-3 py-1.5 font-mono">{dscp}</td>
                      <td className="px-3 py-1.5">
                        {isEditing ? (
                          <select
                            value={priority}
                            onChange={(e) =>
                              setPriority(Number(e.target.value))
                            }
                            className="rounded-md border border-border px-2 py-0.5 text-xs"
                          >
                            {PRIORITY_OPTIONS.map((p) => (
                              <option key={p.value} value={p.value}>
                                {p.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          r.priority_label
                        )}
                      </td>
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
