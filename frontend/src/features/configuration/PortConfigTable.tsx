/**
 * PortConfigTable — row-per-port list with a modal edit dialog.
 *
 * Phase 3 Task 3.5b: per-port configuration (enable / rename / speed+duplex
 * mode / flow control). Not lockout-risky — no host confirmation; the
 * pre-write autobackup on the backend side is rollback enough.
 *
 * A modal is used instead of inline editing because `SetPortConfigRequest`
 * has enough fields (name + admin + mode + flow) that an inline row gets
 * cramped, and the hpSwitchPortFastEtherMode select has 9 options.
 */
import { apiErrorMessage } from "@/api/client";
import { useEffect, useState } from "react";
import { useServerSync } from "@/lib/useServerSync";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  usePortForm,
  usePortsConfig,
  useSetPortConfig,
  type PortConfig,
  type PortMode,
  type SetPortConfigRequest,
} from "@/api/hooks/useConfiguration";

// Mirror backend PortMode IntEnum. Values 1..11 (no 6 — unused).
const MODE_LABELS: Record<PortMode, string> = {
  1: "HDX 10",
  2: "HDX 100",
  3: "FDX 10",
  4: "FDX 100",
  5: "Auto",
  7: "Auto-10",
  8: "Auto-100",
  9: "Auto-1000",
  11: "Auto-10/100",
};
const MODE_OPTIONS: PortMode[] = [1, 2, 3, 4, 5, 7, 8, 9, 11];

// Half-duplex modes — flow control is not valid with these (enforced by
// the backend's SetPortConfigRequest validator).
const HDX_MODES = new Set<PortMode>([1, 2]);

export function PortConfigTable() {
  const ports = usePortsConfig();
  const [editingPort, setEditingPort] = useState<number | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const rows = ports.data?.ports ?? [];

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Per-port configuration
        </h4>
        {ports.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {ports.error instanceof Error && (
        <ErrorBanner className="mb-3">
          <p className="font-medium">Failed to load port config</p>
          <p className="mt-1 break-all">{ports.error.message}</p>
          <button
            type="button"
            onClick={() => ports.refetch()}
            className="mt-2 rounded-md border border-red-400 dark:border-red-900 bg-card px-3 py-1.5 text-sm font-medium text-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
          >
            Retry
          </button>
        </ErrorBanner>
      )}

      {lastResult && (
        <p className="mb-3 text-sm italic text-foreground">{lastResult}</p>
      )}

      <div className="overflow-x-auto rounded border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left">Port</th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Enabled</th>
              <th className="px-3 py-2 text-left">Current mode</th>
              <th className="px-3 py-2 text-left">Flow control</th>
              <th className="px-3 py-2 text-left">Trunk</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.length === 0 && !ports.isLoading && (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-3 text-center text-muted-foreground"
                >
                  No ports reported.
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <PortRow
                key={row.port}
                row={row}
                onEdit={() => {
                  setLastResult(null);
                  setEditingPort(row.port);
                }}
              />
            ))}
          </tbody>
        </table>
      </div>

      {editingPort !== null && (
        <EditPortDialog
          port={editingPort}
          onClose={() => setEditingPort(null)}
          onSaved={(msg) => {
            setEditingPort(null);
            setLastResult(msg);
          }}
        />
      )}
    </section>
  );
}

function PortRow({
  row,
  onEdit,
}: {
  row: PortConfig;
  onEdit: () => void;
}) {
  return (
    <tr>
      <td className="px-3 py-2 font-mono">{row.port}</td>
      <td className="px-3 py-2">{row.port_name.trim() || "—"}</td>
      <td className="px-3 py-2">{row.enabled ? "Yes" : "No"}</td>
      <td className="px-3 py-2">{row.config_mode}</td>
      <td className="px-3 py-2">{row.flow_control ? "Enabled" : "Disabled"}</td>
      <td className="px-3 py-2">{row.trunk.trim() || "—"}</td>
      <td className="px-3 py-2 text-right">
        <button
          type="button"
          onClick={onEdit}
          className="rounded border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted"
        >
          Edit…
        </button>
      </td>
    </tr>
  );
}

function EditPortDialog({
  port,
  onClose,
  onSaved,
}: {
  port: number;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const form = usePortForm(port);
  const mutation = useSetPortConfig();

  const [name, setName] = useState("");
  const [adminEnabled, setAdminEnabled] = useState(true);
  const [mode, setMode] = useState<PortMode>(5);
  const [flowControl, setFlowControl] = useState(false);

  // Seed local state once the form loads (render-phase sync).
  useServerSync(form.data, (data) => {
    setName(data.port_name);
    setAdminEnabled(data.admin_enabled);
    setMode(data.mode);
    setFlowControl(data.flow_control_enabled);
  });

  // Esc-to-close (only when not busy).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !mutation.isPending) {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mutation.isPending, onClose]);

  // The backend rejects flow-control=true with a half-duplex mode; disable
  // the checkbox rather than relying on a server 422 for UX. The submitted
  // value MUST be the same one the checkbox displays (effectiveFlow) — the
  // raw flowControl state can be stale-true while the UI shows forced-off.
  const flowControlForbidden = HDX_MODES.has(mode);
  const effectiveFlow = flowControlForbidden ? false : flowControl;

  const handleSave = () => {
    const request: SetPortConfigRequest = {
      // `ports` is re-pinned by the backend from the URL; we still send
      // [port] so the body is internally consistent.
      ports: [port],
      // Sent verbatim — trimming here would silently rewrite names that
      // legitimately carry edge whitespace on the switch (audit F7).
      name,
      admin_enabled: adminEnabled,
      mode,
      flow_control_enabled: effectiveFlow,
    };
    mutation.mutate(
      { port, body: { request } },
      {
        onSuccess: (data) => {
          onSaved(
            data.ok
              ? `Port ${port} updated.`
              : (data.raw_body ?? "Request accepted."),
          );
        },
      },
    );
  };

  const errorMessage =
    apiErrorMessage(mutation.error);

  const canSave =
    !form.isLoading &&
    !mutation.isPending &&
    form.data !== undefined &&
    (name.trim().length > 0 || form.data.port_name === "");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={() => !mutation.isPending && onClose()}
    >
      <div
        className="w-full max-w-md rounded-lg bg-card p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h5 className="text-base font-semibold text-foreground">
          Edit port {port}
        </h5>
        <p className="mt-0.5 text-xs text-muted-foreground">
          A pre-write backup is taken automatically before the change is
          applied.
        </p>

        {form.isLoading && (
          <div className="mt-4 space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-8 animate-pulse rounded border border-border bg-muted"
              />
            ))}
          </div>
        )}

        {form.error instanceof Error && (
          <ErrorBanner className="mt-4">
            <p className="font-medium">Failed to load port form</p>
            <p className="mt-1 break-all">{form.error.message}</p>
          </ErrorBanner>
        )}

        {form.data && (
          <div className="mt-4 grid gap-3">
            <div>
              <label
                htmlFor="port-name"
                className="block text-xs font-medium text-foreground"
              >
                Port name
              </label>
              <input
                id="port-name"
                type="text"
                value={name}
                maxLength={64}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Must not contain <code className="font-mono">~</code>.
              </p>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={adminEnabled}
                onChange={(e) => setAdminEnabled(e.target.checked)}
              />
              <span>Port enabled (admin)</span>
            </label>

            <div>
              <label
                htmlFor="port-mode"
                className="block text-xs font-medium text-foreground"
              >
                Speed / duplex
              </label>
              <select
                id="port-mode"
                value={mode}
                onChange={(e) => setMode(Number(e.target.value) as PortMode)}
                className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {MODE_OPTIONS.map((m) => (
                  <option key={m} value={m}>
                    {MODE_LABELS[m]}
                  </option>
                ))}
              </select>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={effectiveFlow}
                disabled={flowControlForbidden}
                onChange={(e) => setFlowControl(e.target.checked)}
              />
              <span>
                Flow control enabled
                {flowControlForbidden && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    (not allowed with half-duplex modes)
                  </span>
                )}
              </span>
            </label>
          </div>
        )}

        {errorMessage && (
          <ErrorBanner title="Save failed" className="mt-4">
            {errorMessage}
          </ErrorBanner>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={mutation.isPending}
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!canSave}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
          >
            {mutation.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
