/**
 * CosTableCard — application → priority map (``/cgi/cosapp`` + ``cosappf``).
 *
 * The backend exposes:
 *   GET /qos/cos       -> CosAppList  (rows already include resolved DSCP +
 *                                      priority labels the switch rendered)
 *   PUT /qos/cos       -> QosWriteAck (Add / Replace / Delete one row)
 *
 * The single PUT shape matches the legacy applet's wire format: a write
 * carries `action`, `app_id`, `protocol`, and optional `port`, `dscp`,
 * `priority_8021p`, `policy_mode`. The UI below lets the operator pick a
 * row to delete or add a new row with a user-defined app_id (0 + port).
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useQosCos,
  useSetQosCos,
  type SetCosApptRequest,
  type ApplyPolicy,
} from "@/api/hooks/useConfiguration";

const POLICY_OPTIONS: { value: ApplyPolicy; label: string }[] = [
  { value: 1, label: "No Override" },
  { value: 2, label: "802.1p priority" },
  { value: 3, label: "DSCP" },
];

export function CosTableCard() {
  const query = useQosCos();
  const mutation = useSetQosCos();

  const [form, setForm] = useState<{
    app_id: number;
    protocol: "TCP" | "UDP";
    port: string;
    policy: ApplyPolicy;
    dscp: string;
    priority_8021p: string;
  }>({
    app_id: 0,
    protocol: "TCP",
    port: "",
    policy: 1,
    dscp: "",
    priority_8021p: "",
  });
  const [lastResult, setLastResult] = useState<string | null>(null);

  const entries = query.data?.entries ?? [];

  const submitAdd = () => {
    setLastResult(null);
    mutation.reset();
    const req: SetCosApptRequest = {
      action: "Add",
      app_id: form.app_id,
      protocol: form.protocol,
      policy_mode: form.policy,
    };
    if (form.app_id === 0 && form.port) req.port = Number(form.port);
    if (form.policy === 3 && form.dscp) req.dscp = Number(form.dscp);
    if (form.policy === 2 && form.priority_8021p)
      req.priority_8021p = Number(form.priority_8021p);
    mutation.mutate(
      { request: req },
      {
        onSuccess: () => {
          setLastResult("Entry added.");
          void query.refetch();
        },
      },
    );
  };

  const submitDelete = (appId: number, port: number, protocol: "TCP" | "UDP") => {
    setLastResult(null);
    mutation.reset();
    mutation.mutate(
      {
        request: {
          action: "Delete",
          app_id: appId,
          protocol,
          port,
          policy_mode: 1,
        },
      },
      {
        onSuccess: () => {
          setLastResult(`Deleted ${protocol} :${port}.`);
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
          CoS — application priority
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <ErrorBanner className="mb-3">
          <p className="font-medium">Failed to load cos-app table</p>
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
                  <th className="px-3 py-2 text-left">Application</th>
                  <th className="px-3 py-2 text-left">Port</th>
                  <th className="px-3 py-2 text-left">Proto</th>
                  <th className="px-3 py-2 text-left">DSCP</th>
                  <th className="px-3 py-2 text-left">Priority</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.length === 0 && (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-3 py-3 text-center text-xs italic text-muted-foreground"
                    >
                      No application priority entries.
                    </td>
                  </tr>
                )}
                {entries.map((e, i) => (
                  <tr key={`${e.application_name}-${e.port_number}-${i}`}>
                    <td className="px-3 py-1.5 font-mono">
                      {e.application_name}
                    </td>
                    <td className="px-3 py-1.5">{e.port_number}</td>
                    <td className="px-3 py-1.5">{e.type}</td>
                    <td className="px-3 py-1.5">{e.dscp}</td>
                    <td className="px-3 py-1.5">{e.priority}</td>
                    <td className="px-3 py-1.5 text-right">
                      <button
                        type="button"
                        onClick={() =>
                          submitDelete(0, e.port_number, e.type as "TCP" | "UDP")
                        }
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
                <span className="block text-foreground">App id</span>
                <input
                  type="number"
                  min={0}
                  max={58}
                  value={form.app_id}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      app_id: Number(e.target.value),
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                />
                <span className="mt-0.5 block text-[10px] text-muted-foreground">
                  0 = user-defined (port required)
                </span>
              </label>
              <label className="text-xs">
                <span className="block text-foreground">Protocol</span>
                <select
                  value={form.protocol}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      protocol: e.target.value as "TCP" | "UDP",
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm"
                >
                  <option value="TCP">TCP</option>
                  <option value="UDP">UDP</option>
                </select>
              </label>
              <label className="text-xs">
                <span className="block text-foreground">Port (user-defined)</span>
                <input
                  type="number"
                  min={1}
                  max={65535}
                  value={form.port}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, port: e.target.value }))
                  }
                  disabled={form.app_id !== 0}
                  className="mt-1 w-full rounded-md border border-border px-2 py-1 text-sm disabled:bg-muted"
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
                disabled={mutation.isPending}
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
