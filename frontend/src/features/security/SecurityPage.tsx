/**
 * Security page (Task 3.4).
 *
 * Vertical stack of six cards. The three lockout-risky writes are grouped
 * at the top, then the per-port table, then the read-only summaries:
 *   1. DevicePasswordsCard  — Operator + Manager credentials (lockout-risky, worst)
 *   2. WebAccessCard        — HTTP/HTTPS toggle + SSL port (lockout-risky)
 *   3. WebManagersCard      — Authorized-Manager IP whitelist (lockout-risky)
 *   4. PerPortSecurityCard  — Per-port learn-mode + action table
 *   5. IntrusionLogCard     — Intrusion events + reset-flags
 *   6. SslStateCard         — Read-only SSL state summary
 */
import { DevicePasswordsCard } from "./DevicePasswordsCard";
import { WebAccessCard } from "./WebAccessCard";
import { WebManagersCard } from "./WebManagersCard";
import { PerPortSecurityCard } from "./PerPortSecurityCard";
import { IntrusionLogCard } from "./IntrusionLogCard";
import { SslStateCard } from "./SslStateCard";

export function SecurityPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-lg font-semibold">Security</h2>
        <p className="mt-0.5 text-xs text-neutral-500">
          Manage device passwords, web-access mode, authorized managers,
          per-port security, and the SSL subsystem. Lockout-risky writes
          require typing the switch IP to confirm and take a pre-write
          backup automatically.
        </p>
      </div>

      <div className="grid gap-4">
        <DevicePasswordsCard />
        <WebAccessCard />
        <WebManagersCard />
        <PerPortSecurityCard />
        <IntrusionLogCard />
        <SslStateCard />
      </div>
    </div>
  );
}
