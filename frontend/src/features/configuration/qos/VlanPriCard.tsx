/**
 * VlanPriCard — VLAN priority assignment (``/cgi/cosvlan`` / ``cosvlanf``).
 *
 * Each row assigns either a DSCP or an 802.1p priority to a VLAN. The
 * two are mutually exclusive on the wire; the UI enforces this with a
 * "mode" toggle.
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useQosVlanPri,
  useSetQosVlanPri,
  type SetCosVlanPriRequest,
} from "@/api/hooks/useConfiguration";

type Mode = "dscp" | "priority";

export function VlanPriCard() {
  const query = useQosVlanPri();
  const mutation = useSetQosVlanPri();

  const [form, setForm] = useState<{
    vlan_id: string;
    mode: Mode;
    value: string;
  }>({ vlan_id: "", mode: "dscp", value: "" });
  const [lastResult, setLastResult] = useState<string | null>(null);

  const entries = query.data?.entries ?? [];

  const submit = () => {
    setLastResult(null);
    mutation.reset();
    if (!form.vlan_id || !form.value) return;
    const req: SetCosVlanPriRequest = {
      vlan_id: Number(form.vlan_id),
      dscp: form.mode === "dscp" ? Number(form.value) : 255,
      priority_8021p: form.mode === "priority" ? Number(form.value) : 255,
    };
    mutation.mutate(
      { request: req },
      {
        onSuccess: () => {
          setLastResult(`Applied to VLAN ${form.vlan_id}.`);
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
          CoS — VLAN priority
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <ErrorBanner className="mb-3">
          <p className="font-medium">Failed to load VLAN priority entries</p>
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
          <div className="overflow-x-auto rounded border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">VLAN id</th>
                  <th className="px-3 py-2 text-left">Label</th>
                  <th className="px-3 py-2 text-left">DSCP policy</th>
                  <th className="px-3 py-2 text-left">Priority</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.length === 0 && (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-3 py-3 text-center text-xs italic text-muted-foreground"
                    >
                      No VLAN priority entries.
                    </td>
                  </tr>
                )}
                {entries.map((e) => (
                  <tr key={e.vlan_id}>
                    <td className="px-3 py-1.5 font-mono">{e.vlan_id}</td>
                    <td className="px-3 py-1.5">{e.vlan_label}</td>
                    <td className="px-3 py-1.5">{e.dscp_policy}</td>
                    <td className="px-3 py-1.5">{e.priority}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 rounded border border-dashed border-border bg-muted p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Assign priority
            </p>
            <div className="grid gap-2 sm:grid-cols-3">
              <label className="text-xs">
                <span className="block text-foreground">VLAN id</span>
                <input
                  type="number"
                  min={1}
                  max={4094}
                  value={form.vlan_id}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, vlan_id: e.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                />
              </label>
              <label className="text-xs">
                <span className="block text-foreground">Kind</span>
                <select
                  value={form.mode}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      mode: e.target.value as Mode,
                      value: "",
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                >
                  <option value="dscp">DSCP</option>
                  <option value="priority">802.1p</option>
                </select>
              </label>
              <label className="text-xs">
                <span className="block text-foreground">
                  {form.mode === "dscp" ? "DSCP (0–63)" : "Priority (0–7)"}
                </span>
                <input
                  type="number"
                  min={0}
                  max={form.mode === "dscp" ? 63 : 7}
                  value={form.value}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, value: e.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                />
              </label>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                onClick={submit}
                disabled={
                  !form.vlan_id || !form.value || mutation.isPending
                }
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
              >
                {mutation.isPending ? "Applying…" : "Apply"}
              </button>
              {lastResult && (
                <span className="text-sm italic text-foreground">
                  {lastResult}
                </span>
              )}
            </div>
          </div>

          {errorMessage && (
            <ErrorBanner title="Request failed" className="mt-3">
              {errorMessage}
            </ErrorBanner>
          )}
        </>
      )}
    </section>
  );
}
