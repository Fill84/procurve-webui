/**
 * QosSection — orchestrates the five QoS sub-cards plus the master mode.
 *
 * Why does this wrapper exist instead of dropping the cards directly in
 * ConfigurationPage?
 *
 * The 2810 firmware does not expose a dedicated read for the current QoS
 * master mode (``CosTosMode``). The switch's own applet infers the mode
 * from priority labels rendered in each sub-table. We replicate that
 * imperfection here:
 *
 *   - We keep a local ``mode`` state seeded to ``IP_PRECEDENCE`` (2) —
 *     the common default for this firmware.
 *   - ``QosModeSelector`` owns the PUT; on success it calls ``onModeChange``
 *     so this wrapper updates its state.
 *   - Sub-cards are gated on the mode:
 *       * mode = Disabled (1)      → show all cards (read-only intent, but
 *                                    the backend accepts writes regardless
 *                                    — the user may still want to stage
 *                                    rows before re-enabling).
 *       * mode = IP Precedence (2) → show CoS application / user / VLAN
 *                                    priority and the protocol-priority
 *                                    placeholder. Hide DSCP + DiffServ.
 *       * mode = DiffServ (3)      → show DSCP map + DiffServ table.
 *                                    Hide the CoS tables.
 *
 * This gating is "imperfect" in the sense the plan describes: the mode is
 * not read from the switch, so if another admin changes it out-of-band the
 * UI won't know. We surface this in the selector card's own help text.
 */
import { useState } from "react";
import type { CosTosMode } from "@/api/hooks/useConfiguration";
import { QosModeSelector } from "./QosModeSelector";
import { CosTableCard } from "./CosTableCard";
import { UserPriCard } from "./UserPriCard";
import { VlanPriCard } from "./VlanPriCard";
import { DscpTableCard } from "./DscpTableCard";
import { DiffservCard } from "./DiffservCard";

export function QosSection() {
  // Default to IP Precedence (2) — the canonical CoS mode on this firmware.
  const [mode, setMode] = useState<CosTosMode>(2);

  const showCos = mode === 1 || mode === 2;
  const showDscp = mode === 1 || mode === 3;

  return (
    <div className="grid gap-4">
      <QosModeSelector mode={mode} onModeChange={setMode} />

      {showCos && (
        <>
          <CosTableCard />
          <UserPriCard />
          <VlanPriCard />
        </>
      )}

      {showDscp && (
        <>
          <DscpTableCard />
          <DiffservCard />
        </>
      )}
    </div>
  );
}
