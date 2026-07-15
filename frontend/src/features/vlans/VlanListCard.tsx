/**
 * VlanListCard — all VLANs with create / rename / delete.
 *
 * LOCKOUT RISK: deleting (or renaming away from) the VLAN that carries
 * management traffic severs this UI's own path to the switch. The firmware
 * refuses some of these itself (e.g. deleting the primary VLAN) and its
 * error message is surfaced verbatim. Every write goes through the shared
 * DangerConfirmDialog with the switch IP as the friction value.
 *
 * Client-side validation mirrors the backend model: VLAN id 1..4094, name
 * 1..12 chars, no spaces, no '~' (the wire delimiter).
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { DangerConfirmDialog } from "@/components/ui/DangerConfirmDialog";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useIdentity } from "@/api/hooks/useIdentity";
import {
  useAddVlan,
  useDeleteVlans,
  useRenameVlan,
  useVlans,
  type Vlan,
} from "@/api/hooks/useVlans";

type PendingOp =
  | { kind: "add"; vlanId: number; name: string }
  | { kind: "delete"; row: Vlan }
  | { kind: "rename"; row: Vlan; name: string };

/** Shared name rule (backend: min 1, max 12, no spaces, no '~'). */
function vlanNameError(name: string): string | null {
  if (name.length === 0) return "Name is required.";
  if (name.length > 12) return "Name must be at most 12 characters.";
  if (name.includes(" ")) return "Name cannot contain spaces.";
  if (name.includes("~")) return "Name cannot contain '~'.";
  return null;
}

export function VlanListCard({
  selectedId,
  onSelect,
}: {
  selectedId: number | null;
  onSelect: (vlanId: number | null) => void;
}) {
  const identity = useIdentity();
  const vlans = useVlans();
  const addVlan = useAddVlan();
  const deleteVlans = useDeleteVlans();
  const renameVlan = useRenameVlan();

  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [renameDraft, setRenameDraft] = useState<{
    vlanId: number;
    name: string;
  } | null>(null);
  const [pending, setPending] = useState<PendingOp | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const expectedIp = identity.data?.ip_address ?? "";
  const rows = vlans.data?.vlans ?? [];

  // ---- new-VLAN validation -------------------------------------------
  const idTrimmed = newId.trim();
  const parsedId = /^\d+$/.test(idTrimmed) ? Number(idTrimmed) : null;
  const idError =
    idTrimmed === ""
      ? null
      : parsedId === null || parsedId < 1 || parsedId > 4094
        ? "VLAN id must be 1..4094."
        : rows.some((v) => v.vlan_id === parsedId)
          ? `VLAN ${parsedId} already exists.`
          : null;
  const nameError = newName === "" ? null : vlanNameError(newName);
  const canAdd =
    idTrimmed !== "" &&
    newName !== "" &&
    !idError &&
    !nameError &&
    !!expectedIp;

  const activeMutation =
    pending?.kind === "add"
      ? addVlan
      : pending?.kind === "delete"
        ? deleteVlans
        : renameVlan;

  const resetFeedback = () => {
    setLastResult(null);
    addVlan.reset();
    deleteVlans.reset();
    renameVlan.reset();
  };

  const requestAdd = () => {
    if (!canAdd || parsedId === null) return;
    resetFeedback();
    setPending({ kind: "add", vlanId: parsedId, name: newName });
  };

  const requestDelete = (row: Vlan) => {
    resetFeedback();
    setPending({ kind: "delete", row });
  };

  const requestRename = (row: Vlan) => {
    if (!renameDraft || vlanNameError(renameDraft.name)) return;
    resetFeedback();
    setPending({ kind: "rename", row, name: renameDraft.name });
  };

  const handleConfirm = () => {
    if (!pending || !expectedIp) return;
    const onSuccess = (message: string) => () => {
      setPending(null);
      setLastResult(message);
    };
    if (pending.kind === "add") {
      addVlan.mutate(
        {
          request: { vlan_id: pending.vlanId, vlan_name: pending.name },
          confirm_switch_host: expectedIp,
        },
        {
          onSuccess: () => {
            onSuccess(`Created VLAN ${pending.vlanId} (${pending.name}).`)();
            setNewId("");
            setNewName("");
          },
        },
      );
    } else if (pending.kind === "delete") {
      deleteVlans.mutate(
        {
          request: { vlan_ids: [pending.row.vlan_id] },
          confirm_switch_host: expectedIp,
        },
        {
          onSuccess: () => {
            onSuccess(`Deleted VLAN ${pending.row.vlan_id}.`)();
            if (selectedId === pending.row.vlan_id) onSelect(null);
          },
        },
      );
    } else {
      renameVlan.mutate(
        {
          vlanId: pending.row.vlan_id,
          body: {
            vlan_name: pending.name,
            confirm_switch_host: expectedIp,
          },
        },
        {
          onSuccess: () => {
            onSuccess(
              `Renamed VLAN ${pending.row.vlan_id} to "${pending.name}".`,
            )();
            setRenameDraft(null);
          },
        },
      );
    }
  };

  const errorMessage = apiErrorMessage(activeMutation.error);

  const dialogBody = pending ? (
    <div className="space-y-3">
      <ErrorBanner title="Lockout risk">
        {pending.kind === "delete"
          ? "Deleting the VLAN that carries management traffic severs this UI's connection to the switch immediately. The switch refuses to delete the primary VLAN, but any other management path is your responsibility."
          : "VLAN changes apply immediately. If management traffic depends on this VLAN, a wrong change can cut off web access to the switch."}
      </ErrorBanner>
      <div className="rounded border border-border bg-muted p-3 text-sm">
        {pending.kind === "add" && (
          <p>
            <span className="font-semibold">Create:</span> VLAN{" "}
            <span className="font-mono">{pending.vlanId}</span> named{" "}
            <span className="font-mono">{pending.name}</span>
          </p>
        )}
        {pending.kind === "delete" && (
          <p>
            <span className="font-semibold">Delete:</span> VLAN{" "}
            <span className="font-mono">{pending.row.vlan_id}</span> (
            <span className="font-mono">{pending.row.vlan_name}</span>)
          </p>
        )}
        {pending.kind === "rename" && (
          <p>
            <span className="font-semibold">Rename:</span> VLAN{" "}
            <span className="font-mono">{pending.row.vlan_id}</span> from{" "}
            <span className="font-mono">{pending.row.vlan_name}</span> to{" "}
            <span className="font-mono">{pending.name}</span>
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
            VLANs
          </h4>
          {vlans.isLoading && (
            <span className="text-xs text-muted-foreground">Loading…</span>
          )}
        </div>

        {vlans.error instanceof Error && (
          <ErrorBanner className="mb-3">
            Failed to fetch VLANs: {vlans.error.message}
          </ErrorBanner>
        )}

        <div className="overflow-x-auto rounded border border-border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Name</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Untagged</th>
                <th className="px-3 py-2 text-left">Tagged</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.length === 0 && !vlans.isLoading && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-3 py-3 text-center text-muted-foreground"
                  >
                    No VLANs reported.
                  </td>
                </tr>
              )}
              {rows.map((row) => {
                const isSelected = selectedId === row.vlan_id;
                const isRenaming = renameDraft?.vlanId === row.vlan_id;
                const renameError = isRenaming
                  ? vlanNameError(renameDraft.name)
                  : null;
                return (
                  <tr
                    key={row.vlan_id}
                    aria-selected={isSelected}
                    onClick={() =>
                      onSelect(isSelected ? null : row.vlan_id)
                    }
                    className={`cursor-pointer ${
                      isSelected ? "bg-accent" : "hover:bg-muted"
                    }`}
                  >
                    <td className="px-3 py-2 font-mono">{row.vlan_id}</td>
                    <td className="px-3 py-2 font-mono">
                      {isRenaming ? (
                        <input
                          type="text"
                          value={renameDraft.name}
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) =>
                            setRenameDraft({
                              vlanId: row.vlan_id,
                              name: e.target.value,
                            })
                          }
                          aria-invalid={renameError !== null}
                          className={`w-36 rounded-md border px-2 py-1 font-mono text-xs ${
                            renameError
                              ? "border-red-400 dark:border-red-900"
                              : "border-border"
                          }`}
                        />
                      ) : (
                        row.vlan_name
                      )}
                    </td>
                    <td className="px-3 py-2">{row.vlan_type}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {row.untagged_ports}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {row.tagged_ports}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      {isRenaming ? (
                        <>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              requestRename(row);
                            }}
                            disabled={renameError !== null || !expectedIp}
                            className="mr-2 rounded border border-red-300 bg-card px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/40"
                          >
                            Apply…
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRenameDraft(null);
                            }}
                            className="rounded border border-border bg-card px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRenameDraft({
                                vlanId: row.vlan_id,
                                name: row.vlan_name,
                              });
                            }}
                            className="mr-2 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
                          >
                            Rename
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              requestDelete(row);
                            }}
                            className="rounded border border-red-300 bg-card px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/40"
                          >
                            Delete…
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
              <tr className="bg-muted">
                <td className="px-3 py-2">
                  <input
                    type="text"
                    placeholder="ID"
                    value={newId}
                    onChange={(e) => setNewId(e.target.value)}
                    aria-invalid={idError !== null}
                    className={`w-16 rounded-md border px-2 py-1 font-mono text-xs ${
                      idError
                        ? "border-red-400 dark:border-red-900"
                        : "border-border"
                    }`}
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="text"
                    placeholder="Name (≤12 chars)"
                    value={newName}
                    maxLength={12}
                    onChange={(e) => setNewName(e.target.value)}
                    aria-invalid={nameError !== null}
                    className={`w-36 rounded-md border px-2 py-1 font-mono text-xs ${
                      nameError
                        ? "border-red-400 dark:border-red-900"
                        : "border-border"
                    }`}
                  />
                </td>
                <td className="px-3 py-2 text-muted-foreground" colSpan={3}>
                  new static VLAN
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={requestAdd}
                    disabled={!canAdd}
                    className="rounded border border-red-300 bg-card px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/40"
                  >
                    Create…
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {(idError ?? nameError) && (
          <p className="mt-2 text-xs text-red-700 dark:text-red-300">
            {idError ?? nameError}
          </p>
        )}

        <p className="mt-2 text-xs text-muted-foreground">
          Select a row to edit its per-port membership below.
        </p>

        {lastResult && (
          <p className="mt-3 text-sm italic text-foreground">{lastResult}</p>
        )}
      </section>

      <DangerConfirmDialog
        open={pending !== null}
        title={
          pending?.kind === "add"
            ? "Create VLAN"
            : pending?.kind === "delete"
              ? "Delete VLAN"
              : "Rename VLAN"
        }
        body={dialogBody}
        confirmationValue={expectedIp}
        confirmationLabel="Type the switch IP to confirm"
        confirmationHint={confirmationHint}
        confirmationPlaceholder="e.g. 192.168.1.10"
        confirmButtonText={
          pending?.kind === "add"
            ? "Create VLAN"
            : pending?.kind === "delete"
              ? "Delete VLAN"
              : "Rename VLAN"
        }
        busyButtonText="Applying…"
        onConfirm={handleConfirm}
        onCancel={() => setPending(null)}
        busy={activeMutation.isPending}
        error={
          errorMessage ? (
            <ErrorBanner title="Apply failed">{errorMessage}</ErrorBanner>
          ) : null
        }
      />
    </>
  );
}
