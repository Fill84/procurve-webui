/**
 * Configuration page (Task 3.5).
 *
 * Vertical stack of cards, one per sub-tab of the legacy Configuration
 * menu. Task 3.5 ships across five sub-tasks:
 *
 *   3.5a   System info + IP configuration
 *   3.5b   Per-port configuration
 *   3.5c   Device features (IGMP / STP) + fault detection + port mirroring
 *          + device-view admin status (bob-ports)
 *   3.5d   QoS (cos-app / dscp / diffserv / ...)
 *   3.5e   Support URLs
 *
 * 3.5e remains a placeholder until that sub-task lands.
 */
import { SystemInfoCard } from "./SystemInfoCard";
import { IpConfigCard } from "./IpConfigCard";
import { PortConfigTable } from "./PortConfigTable";
import { DeviceFeaturesCard } from "./DeviceFeaturesCard";
import { FaultDetectionCard } from "./FaultDetectionCard";
import { MonitorCard } from "./MonitorCard";
import { BobPortsCard } from "./BobPortsCard";
import { QosSection } from "./qos/QosSection";

export function ConfigurationPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold">Configuration</h2>
        <p className="mt-0.5 text-xs text-neutral-500">
          System identity, network addressing, per-port settings, device
          features, QoS, and support URLs. Lockout-risky writes (like the
          management IP) require typing the switch IP to confirm; every
          write takes a pre-write autobackup.
        </p>
      </div>

      <div className="grid gap-4">
        <SystemInfoCard />
        <IpConfigCard />
        <PortConfigTable />
        <DeviceFeaturesCard />
        <FaultDetectionCard />
        <MonitorCard />
        <BobPortsCard />

        <QosSection />

        <PlaceholderCard
          title="Support URLs"
          note="Coming in Task 3.5e — support URL and management server URL."
        />
      </div>
    </div>
  );
}

function PlaceholderCard({ title, note }: { title: string; note: string }) {
  return (
    <section className="rounded-lg border border-dashed border-neutral-300 bg-neutral-50 p-6">
      <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
        {title}
      </h4>
      <p className="mt-1 text-sm text-neutral-600">{note}</p>
    </section>
  );
}
