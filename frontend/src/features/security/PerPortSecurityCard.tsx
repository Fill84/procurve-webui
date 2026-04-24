/**
 * PerPortSecurityCard — one row per port with inline-edit for learn-mode +
 * action-on-intrusion.
 *
 * Not lockout-risky: per-port security changes are reversible via the
 * pre-write autobackup and do not affect management access. No danger dialog.
 */
import { useState } from "react";
import {
  usePerPort,
  useSetPerport,
  type PortSecurityRow,
  type SetPerportRequest,
} from "@/api/hooks/useSecurity";

const MODE_LABELS: Record<number, string> = {
  1: "Continuous",
  2: "Static",
  5: "Port Access",
};
const ACTION_LABELS: Record<number, string> = {
  1: "None",
  2: "Send alarm",
  3: "Send alarm + disable",
};

export function PerPortSecurityCard() {
  const perPort = usePerPort();
  const setPerport = useSetPerport();

  const [editingPort, setEditingPort] = useState<number | null>(null);
  const [mode, setMode] = useState<1 | 2 | 5>(1);
  const [action, setAction] = useState<1 | 2 | 3>(1);
  const [limit, setLimit] = useState<number>(1);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const startEdit = (row: PortSecurityRow) => {
    setLastResult(null);
    setPerport.reset();
    setEditingPort(row.port);
    const resolvedMode =
      row.address_selection === "Continuous"
        ? 1
        : row.address_selection === "Static"
          ? 2
          : row.address_selection === "Port Access"
            ? 5
            : 1;
    setMode(resolvedMode as 1 | 2 | 5);
    setAction((row.security_action || 1) as 1 | 2 | 3);
    setLimit(row.address_limit || 1);
  };

  const saveEdit = (row: PortSecurityRow) => {
    const request: SetPerportRequest = {
      group: "",
      trunk: row.trunk ? 1 : 0,
      port: row.port,
      indeces: [row.port],
      mode,
      security_action: action,
      address_limit: limit,
    };
    setPerport.mutate(
      { port: row.port, body: { request } },
      {
        onSuccess: (data) => {
          setEditingPort(null);
          setLastResult(
            data.applied
              ? `Port ${row.port} updated.`
              : (data.message ?? "Request accepted."),
          );
        },
      },
    );
  };

  const errorMessage =
    setPerport.error instanceof Error ? setPerport.error.message : null;

  const rows = perPort.data?.rows ?? [];

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Per-port security
        </h4>
        {perPort.isLoading && (
          <span className="text-xs text-neutral-500">Loading…</span>
        )}
      </div>

      {perPort.error instanceof Error && (
        <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          Failed to fetch per-port state: {perPort.error.message}
        </div>
      )}

      {errorMessage && (
        <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-semibold">Update failed</p>
          <p className="mt-1 break-all">{errorMessage}</p>
        </div>
      )}

      {lastResult && (
        <p className="mb-3 text-sm italic text-neutral-700">{lastResult}</p>
      )}

      <div className="overflow-x-auto rounded border border-neutral-200">
        <table className="min-w-full text-sm">
          <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-600">
            <tr>
              <th className="px-3 py-2 text-left">Port</th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Learn mode</th>
              <th className="px-3 py-2 text-left">Action</th>
              <th className="px-3 py-2 text-left">Limit</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200">
            {rows.length === 0 && !perPort.isLoading && (
              <tr>
                <td
                  colSpan={6}
                  className="px-3 py-3 text-center text-neutral-500"
                >
                  No per-port rows.
                </td>
              </tr>
            )}
            {rows.map((row) => {
              const editing = editingPort === row.port;
              return (
                <tr key={row.port}>
                  <td className="px-3 py-2 font-mono">{row.port}</td>
                  <td className="px-3 py-2">{row.port_name.trim() || "—"}</td>
                  <td className="px-3 py-2">
                    {editing ? (
                      <select
                        value={mode}
                        onChange={(e) =>
                          setMode(Number(e.target.value) as 1 | 2 | 5)
                        }
                        className="rounded border border-neutral-300 px-2 py-1 text-xs"
                      >
                        <option value={1}>Continuous</option>
                        <option value={2}>Static</option>
                        <option value={5}>Port Access</option>
                      </select>
                    ) : (
                      (MODE_LABELS[
                        row.address_selection === "Continuous"
                          ? 1
                          : row.address_selection === "Static"
                            ? 2
                            : row.address_selection === "Port Access"
                              ? 5
                              : 0
                      ] ?? row.address_selection)
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {editing ? (
                      <select
                        value={action}
                        onChange={(e) =>
                          setAction(Number(e.target.value) as 1 | 2 | 3)
                        }
                        className="rounded border border-neutral-300 px-2 py-1 text-xs"
                      >
                        <option value={1}>None</option>
                        <option value={2}>Send alarm</option>
                        <option value={3}>Send alarm + disable</option>
                      </select>
                    ) : (
                      (ACTION_LABELS[row.security_action] ??
                        row.security_action)
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono">
                    {editing ? (
                      <input
                        type="number"
                        min={1}
                        max={8}
                        value={limit}
                        onChange={(e) =>
                          setLimit(Number(e.target.value) || 1)
                        }
                        className="w-16 rounded border border-neutral-300 px-2 py-1 text-xs"
                      />
                    ) : (
                      row.address_limit
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {editing ? (
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => setEditingPort(null)}
                          disabled={setPerport.isPending}
                          className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => saveEdit(row)}
                          disabled={setPerport.isPending}
                          className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:bg-blue-300"
                        >
                          {setPerport.isPending ? "Saving…" : "Save"}
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => startEdit(row)}
                        className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs"
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
    </section>
  );
}
