/**
 * WebManagersCard — Authorized-Manager IP whitelist.
 *
 * LOCKOUT RISK: this is a WHITELIST. A bad entry (wrong mask, or deleting
 * your own row) locks the caller out of the web UI IMMEDIATELY. Every
 * add/delete goes through the shared DangerConfirmDialog with the switch IP.
 * New entries are format-validated client-side (IPv4 + mask), and the
 * confirm dialog warns when the prospective whitelist would no longer
 * cover the operator's own client IP (as reported by whoami).
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { entryCovers, isContiguousNetmask, isValidIpv4 } from "@/lib/ipv4";
import { useIdentity } from "@/api/hooks/useIdentity";
import { useWhoami } from "@/api/hooks/useAuth";
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
  const whoami = useWhoami();
  const managers = useWebManagers();
  const setManager = useSetWebManager();

  const [newIp, setNewIp] = useState("");
  const [newMask, setNewMask] = useState("255.255.255.255");
  const [newLevel, setNewLevel] = useState<1 | 2>(2); // Manager
  const [pending, setPending] = useState<PendingOp | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const expectedIp = identity.data?.ip_address ?? "";
  const clientIp = whoami.data?.client_ip ?? null;

  // L7: format-validate before the payload can reach the switch — this is
  // the card whose own warning says a bad entry locks you out immediately.
  const ipTrimmed = newIp.trim();
  const maskTrimmed = newMask.trim() || "255.255.255.255";
  const ipError =
    ipTrimmed !== "" && !isValidIpv4(ipTrimmed)
      ? "Not a valid IPv4 address."
      : null;
  const maskError = !isValidIpv4(maskTrimmed)
    ? "Not a valid IPv4 mask."
    : null;
  const maskWarning =
    !maskError && !isContiguousNetmask(maskTrimmed)
      ? "Mask bits are non-contiguous — double-check this is intended."
      : null;
  const canAdd =
    ipTrimmed !== "" && !ipError && !maskError && !!expectedIp;

  const requestAdd = () => {
    if (!canAdd) return;
    setLastResult(null);
    setManager.reset();
    setPending({
      kind: "add",
      ip: ipTrimmed,
      mask: maskTrimmed,
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
    apiErrorMessage(setManager.error);

  const entries = managers.data?.entries ?? [];

  // Own-IP coverage check (advisory): compute the whitelist as it would
  // look after the pending change; an empty whitelist means no restriction.
  const prospective: Array<{ ip: string; mask: string }> = !pending
    ? []
    : pending.kind === "add"
      ? [...entries, { ip: pending.ip, mask: pending.mask }]
      : entries.filter((e) => e.index !== pending.row.index);
  const ownIpExcluded =
    pending !== null &&
    clientIp !== null &&
    prospective.length > 0 &&
    !prospective.some((e) => entryCovers(e.ip, e.mask, clientIp));

  const dialogBody = pending ? (
    <div className="space-y-3">
      <ErrorBanner title="Lockout risk">
        The authorized-manager list is a whitelist. Changes take effect
        immediately. If your client IP is not covered after the change, you
        will be locked out of the web UI.
      </ErrorBanner>
      {ownIpExcluded && (
        <ErrorBanner title="Your own IP will be locked out">
          After this change, no whitelist entry covers your current client
          IP (<span className="font-mono">{clientIp}</span>) — applying it
          will cut off this session's access to the switch web UI
          immediately.
        </ErrorBanner>
      )}
      <div className="rounded border border-border bg-muted p-3 text-sm">
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
        <span className="font-mono text-foreground">{expectedIp}</span>
      ) : (
        <span className="italic">loading identity…</span>
      )}
    </>
  );

  return (
    <>
      <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Authorized managers
          </h4>
          {managers.isLoading && (
            <span className="text-xs text-muted-foreground">Loading…</span>
          )}
        </div>

        {managers.error instanceof Error && (
          <ErrorBanner className="mb-3">
            Failed to fetch managers: {managers.error.message}
          </ErrorBanner>
        )}

        <div className="overflow-x-auto rounded border border-border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">IP</th>
                <th className="px-3 py-2 text-left">Mask</th>
                <th className="px-3 py-2 text-left">Access</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entries.length === 0 && !managers.isLoading && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-3 py-3 text-center text-muted-foreground"
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
                      className="rounded border border-red-300 bg-card px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/40"
                    >
                      Remove…
                    </button>
                  </td>
                </tr>
              ))}
              <tr className="bg-muted">
                <td className="px-3 py-2 text-muted-foreground">new</td>
                <td className="px-3 py-2">
                  <input
                    type="text"
                    placeholder="IP"
                    value={newIp}
                    onChange={(e) => setNewIp(e.target.value)}
                    aria-invalid={ipError !== null}
                    className={`w-full rounded-md border px-2 py-1 font-mono text-xs ${
                      ipError ? "border-red-400 dark:border-red-900" : "border-border"
                    }`}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="text"
                    placeholder="Mask"
                    value={newMask}
                    onChange={(e) => setNewMask(e.target.value)}
                    aria-invalid={maskError !== null}
                    className={`w-full rounded-md border px-2 py-1 font-mono text-xs ${
                      maskError ? "border-red-400 dark:border-red-900" : "border-border"
                    }`}
                  />
                </td>
                <td className="px-3 py-2">
                  <select
                    value={newLevel}
                    onChange={(e) =>
                      setNewLevel(Number(e.target.value) as 1 | 2)
                    }
                    className="rounded-md border border-border px-2 py-1 text-xs"
                  >
                    <option value={2}>Manager</option>
                    <option value={1}>Operator</option>
                  </select>
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={requestAdd}
                    disabled={!canAdd}
                    className="rounded border border-red-300 bg-card px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/40"
                  >
                    Add…
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {(ipError ?? maskError ?? maskWarning) && (
          <p className="mt-2 text-xs text-red-700 dark:text-red-300">
            {ipError ?? maskError ?? maskWarning}
          </p>
        )}

        {lastResult && (
          <p className="mt-3 text-sm italic text-foreground">{lastResult}</p>
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
            <ErrorBanner title="Apply failed">{errorMessage}</ErrorBanner>
          ) : null
        }
      />
    </>
  );
}
