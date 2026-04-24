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
import { useState } from "react";
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
    mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          DSCP → 802.1p map
        </h4>
        {query.isLoading && (
          <span className="text-xs text-neutral-500">Loading…</span>
        )}
      </div>

      <p className="mb-3 text-xs text-neutral-600">
        64 rows. Edit one at a time — each row is a separate write and a
        separate autobackup on the backend.
      </p>

      {query.error instanceof Error && (
        <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-medium">Failed to load DSCP table</p>
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
          <div className="max-h-96 overflow-auto rounded border border-neutral-200">
            <table className="min-w-full text-sm">
              <thead className="sticky top-0 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-600">
                <tr>
                  <th className="px-3 py-2 text-left">Row</th>
                  <th className="px-3 py-2 text-left">Codepoint</th>
                  <th className="px-3 py-2 text-left">DSCP</th>
                  <th className="px-3 py-2 text-left">Priority</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {rows.map((r) => {
                  const dscp = parseInt(r.codepoint, 2);
                  const isEditing = editing === r.row_index;
                  return (
                    <tr
                      key={r.row_index}
                      className={isEditing ? "bg-amber-50" : undefined}
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
                            className="rounded-md border border-neutral-300 px-2 py-0.5 text-xs"
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
                              className="text-xs text-neutral-600 hover:underline"
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
            <p className="mt-3 text-sm italic text-neutral-700">
              {lastResult}
            </p>
          )}

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
