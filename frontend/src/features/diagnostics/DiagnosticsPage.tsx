/**
 * Diagnostics page (Task 3.3).
 *
 * Vertical stack of four cards:
 *   1. Ping
 *   2. Link test
 *   3. Configuration report
 *   4. Device reset (danger zone, red border)
 */
import { PingCard } from "./PingCard";
import { LinkTestCard } from "./LinkTestCard";
import { ConfigReportCard } from "./ConfigReportCard";
import { DeviceResetCard } from "./DeviceResetCard";

export function DiagnosticsPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold">Diagnostics</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Run ping/link tests, fetch the current running-config, or (with care)
          reset the switch to factory defaults.
        </p>
      </div>

      <div className="grid gap-4">
        <PingCard />
        <LinkTestCard />
        <ConfigReportCard />
        <DeviceResetCard />
      </div>
    </div>
  );
}
