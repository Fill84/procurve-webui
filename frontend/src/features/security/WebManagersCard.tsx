/**
 * WebManagersCard — Authorized-Manager IP whitelist.
 *
 * LOCKOUT RISK: this is a WHITELIST. A bad entry (wrong mask, or deleting
 * your own row) locks the caller out of the web UI IMMEDIATELY. Every
 * add/delete goes through the shared DangerConfirmDialog with the switch IP.
 */
import { useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { useIdentity } from "@/api/hooks/useIdentity";
import {
  useSetWebManager,
  useWebManagers,
  type AuthorizedManager,
  type SetWebManagerBody,
} from "@/api/hooks/useSecurity";

type PendingOp =
  | { kind: "add"; ip: string; mask: string; level: 1 | 2 }
  | { kind: "delete"; row: AuthorizedManager };

export function WebManagersCard() {
  const identity = useIdentity();
  const managers = useWebManagers();
  const setManager = useSetWebManager();

  const [newIp, setNewIp] = useState("");
  const [newMask, setNewMask] = useState("255.255.255.255");
  const [newLevel, setNewLevel] = useState<1 | 2>(2); // Manager
  const [pending, setPending] = useState<PendingOp | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const expectedIp = identity.data?.ip_address ?? "";

  const requestAdd = () => {
    if (!newIp.trim()) return;
    setLastResult(null);
    setManager.reset();
    setPending({
      kind: "add",
      ip: newIp.trim(),
      mask: newMask.trim() || "255.255.255.255",
      level: newLevel,
    });
  };

  const requestDelete = (row: AuthorizedManager) => {
    setLastResult(null);
    setManager.reset();
    setPending({ kind: "delete", row });
  };

  const handleConfirm = () => {
    if (!pending || !expectedIp) return;
    let body: SetWebManagerBody;
    if (pending.kind === "add") {
      body = {
        request: {
          action: 1,
          ip: pending.ip,
          mask: pending.mask,
          level: pending.level,
          indeces: [],
        },
        confirm_switch_host: expectedIp,
      };
    } else {
      body = {
        request: {
          action: 3,
          indeces: [pending.row.index],
        },
        confirm_switch_host: expectedIp,
      };
    }
    setManager.mutate(body, {
      onSuccess: (data) => {
        setPending(null);
        setLastResult(
          data.applied
            ? pending.kind === "add"
              ? `Added ${pending.ip}/${pending.mask}.`
              : `Deleted entry #${pending.row.index}.`
            : (data.message ?? "Request accepted."),
        );
        setNewIp("");
      },
    });
  };

  const errorMessage =
    setManager.error instanceof Error ? setManager.error.message : null;

  const entries = managers.data?.entries ?? [];

  const dialogBody = pending ? (
    <div className="space-y-3">
      <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
        <p className="font-semibold">Lockout risk</p>
        <p className="mt-1">
          The authorized-manager list is a whitelist. Changes take effect
          immediately. If your client IP is not covered after the change, you
          will be locked out of the web UI.
        </p>
      </div>
      <div className="rounded border border-neutral-200 bg-neutral-50 p-3 text-sm">
        {pending.kind === "add" ? (
          <p>
            <span className="font-semibold">Add:</span>{" "}
            <span className="font-mono">
              {pending.ip}/{pending.mask}
            </span>{" "}
            as {pending.level === 2 ? "Manager" : "Operator"}
          </p>
        ) : (
          <p>
            <span className="font-semibold">Delete:</span> #
            {pending.row.index} —{" "}
            <span className="font-mono">
              {pending.row.ip}/{pending.row.mask}
            </span>{" "}
            ({pending.row.access_level})
          </p>
        )}
      </div>
    </div>
  ) : (
    <></>
  );

  const confirmationHint = (
    <>
      Expected:{" "}
      {expectedIp ? (
        <span className="font-mono text-neutral-700">{expectedIp}</span>
      ) : (
        <span className="italic">loading identity…</span>
      )}
    </>
  );

  return (
    <>
      <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
            Authorized managers
          </h4>
          {managers.isLoading && (
            <span className="text-xs text-neutral-500">Loading…</span>
          )}
        </div>

        {managers.error instanceof Error && (
          <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
            Failed to fetch managers: {managers.error.message}
          </div>
        )}

        <div className="overflow-x-auto rounded border border-neutral-200">
          <table className="min-w-full text-sm">
            <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-600">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">IP</th>
                <th className="px-3 py-2 text-left">Mask</th>
                <th className="px-3 py-2 text-left">Access</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200">
              {entries.length === 0 && !managers.isLoading && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-3 py-3 text-center text-neutral-500"
                  >
                    No authorized-manager entries.
                  </td>
                </tr>
              )}
              {entries.map((row) => (
                <tr key={row.index}>
                  <td className="px-3 py-2 font-mono">{row.index}</td>
                  <td className="px-3 py-2 font-mono">{row.ip}</td>
                  <td className="px-3 py-2 font-mono">{row.mask}</td>
                  <td className="px-3 py-2">{row.access_level}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => requestDelete(row)}
                      className="rounded border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                    >
                      Remove…
                    </button>
                  </td>
                </tr>
              ))}
              <tr className="bg-neutral-50">
                <td className="px-3 py-2 text-neutral-400">new</td>
                <td className="px-3 py-2">
                  <input
                    type="text"
                    placeholder="IP"
                    value={newIp}
                    onChange={(e) => setNewIp(e.target.value)}
                    className="w-full rounded-md border border-neutral-300 px-2 py-1 font-mono text-xs"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="text"
                    placeholder="Mask"
                    value={newMask}
                    onChange={(e) => setNewMask(e.target.value)}
                    className="w-full rounded-md border border-neutral-300 px-2 py-1 font-mono text-xs"
                  />
                </td>
                <td className="px-3 py-2">
                  <select
                    value={newLevel}
                    onChange={(e) =>
                      setNewLevel(Number(e.target.value) as 1 | 2)
                    }
                    className="rounded-md border border-neutral-300 px-2 py-1 text-xs"
                  >
                    <option value={2}>Manager</option>
                    <option value={1}>Operator</option>
                  </select>
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={requestAdd}
                    disabled={!newIp.trim() || !expectedIp}
                    className="rounded border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    Add…
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {lastResult && (
          <p className="mt-3 text-sm italic text-neutral-700">{lastResult}</p>
        )}
      </section>

      <DangerConfirmDialog
        open={pending !== null}
        title={
          pending?.kind === "delete"
            ? "Delete authorized-manager entry"
            : "Add authorized-manager entry"
        }
        body={dialogBody}
        confirmationValue={expectedIp}
        confirmationLabel="Type the switch IP to confirm"
        confirmationHint={confirmationHint}
        confirmationPlaceholder="e.g. 192.168.1.10"
        confirmButtonText={
          pending?.kind === "delete" ? "Delete entry" : "Add entry"
        }
        busyButtonText="Applying…"
        onConfirm={handleConfirm}
        onCancel={() => setPending(null)}
        busy={setManager.isPending}
        error={
          errorMessage ? (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              <p className="font-semibold">Apply failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          ) : null
        }
      />
    </>
  );
}
