/**
 * UserPriCard — per-device (IP) QoS entries (``/cgi/cosuser`` / ``cosuserf``).
 *
 * Lists IP addresses with their resolved DSCP / priority labels, lets the
 * operator delete a row or add a new one.
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useQosUserPri,
  useSetQosUserPri,
  type SetCosUserPriRequest,
  type ApplyPolicy,
} from "@/api/hooks/useConfiguration";

const POLICY_OPTIONS: { value: ApplyPolicy; label: string }[] = [
  { value: 1, label: "No Override" },
  { value: 2, label: "802.1p priority" },
  { value: 3, label: "DSCP" },
];

export function UserPriCard() {
  const query = useQosUserPri();
  const mutation = useSetQosUserPri();

  const [form, setForm] = useState({
    address: "",
    policy: 1 as ApplyPolicy,
    dscp: "",
    priority_8021p: "",
  });
  const [lastResult, setLastResult] = useState<string | null>(null);

  const entries = query.data?.entries ?? [];

  const submitAdd = () => {
    setLastResult(null);
    mutation.reset();
    if (!form.address) return;
    const req: SetCosUserPriRequest = {
      action: "Add",
      address: form.address,
      policy_mode: form.policy,
    };
    if (form.policy === 3 && form.dscp) req.dscp = Number(form.dscp);
    if (form.policy === 2 && form.priority_8021p)
      req.priority_8021p = Number(form.priority_8021p);
    mutation.mutate(
      { request: req },
      {
        onSuccess: () => {
          setLastResult(`Added ${form.address}.`);
          void query.refetch();
        },
      },
    );
  };

  const submitDelete = (address: string) => {
    setLastResult(null);
    mutation.reset();
    mutation.mutate(
      { request: { action: "Delete", address, policy_mode: 1 } },
      {
        onSuccess: () => {
          setLastResult(`Deleted ${address}.`);
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
          CoS — device priority
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <ErrorBanner className="mb-3">
          <p className="font-medium">Failed to load device-priority entries</p>
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
                  <th className="px-3 py-2 text-left">IP address</th>
                  <th className="px-3 py-2 text-left">DSCP policy</th>
                  <th className="px-3 py-2 text-left">Priority</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.length === 0 && (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-3 py-3 text-center text-xs italic text-muted-foreground"
                    >
                      No per-device priority entries.
                    </td>
                  </tr>
                )}
                {entries.map((e, i) => (
                  <tr key={`${e.ip_address}-${i}`}>
                    <td className="px-3 py-1.5 font-mono">{e.ip_address}</td>
                    <td className="px-3 py-1.5">{e.dscp_policy}</td>
                    <td className="px-3 py-1.5">{e.priority}</td>
                    <td className="px-3 py-1.5 text-right">
                      <button
                        type="button"
                        onClick={() => submitDelete(e.ip_address)}
                        disabled={mutation.isPending}
                        className="text-xs text-red-600 hover:underline disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 rounded border border-dashed border-border bg-muted p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Add entry
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs">
                <span className="block text-foreground">IP address</span>
                <input
                  type="text"
                  value={form.address}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, address: e.target.value }))
                  }
                  placeholder="10.0.0.5"
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm font-mono"
                />
              </label>
              <label className="text-xs">
                <span className="block text-foreground">Policy mode</span>
                <select
                  value={form.policy}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      policy: Number(e.target.value) as ApplyPolicy,
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                >
                  {POLICY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              {form.policy === 3 && (
                <label className="text-xs">
                  <span className="block text-foreground">DSCP (0–63)</span>
                  <input
                    type="number"
                    min={0}
                    max={63}
                    value={form.dscp}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, dscp: e.target.value }))
                    }
                    className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                  />
                </label>
              )}
              {form.policy === 2 && (
                <label className="text-xs">
                  <span className="block text-foreground">
                    802.1p priority (0–7)
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={7}
                    value={form.priority_8021p}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        priority_8021p: e.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                  />
                </label>
              )}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                onClick={submitAdd}
                disabled={!form.address || mutation.isPending}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
              >
                {mutation.isPending ? "Applying…" : "Add"}
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
