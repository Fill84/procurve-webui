/**
 * VLANs page (Phase 4, F1 — the headline feature).
 *
 * Two cards:
 *   1. VlanListCard        — all VLANs (getVLANAll): create / rename / delete
 *   2. VlanMembershipCard  — per-port membership editor for the selected VLAN
 *
 * EVERY write on this page is lockout-risky (spec §8.3 "careful" tier):
 * deleting or re-homing the VLAN that carries management traffic — or
 * flipping the untagged membership of the operator's own uplink port —
 * severs this UI's path to the switch. All writes require typing the
 * switch IP (DangerConfirmDialog) and take a pre-write backup server-side.
 */
import { useState } from "react";
import { VlanListCard } from "./VlanListCard";
import { VlanMembershipCard } from "./VlanMembershipCard";

export function VlansPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold">VLANs</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          802.1Q VLAN configuration — create, rename, delete, and per-port
          membership. Every change here is lockout-risky: it requires typing
          the switch IP to confirm and takes a pre-write backup
          automatically.
        </p>
      </div>

      <div className="grid gap-4">
        <VlanListCard selectedId={selectedId} onSelect={setSelectedId} />
        <VlanMembershipCard vlanId={selectedId} />
      </div>
    </div>
  );
}
