/**
 * Security page (Task 3.4).
 *
 * Vertical stack of five cards:
 *   1. WebAccessCard        — HTTP/HTTPS toggle + SSL port (lockout-risky)
 *   2. WebManagersCard      — Authorized-Manager IP whitelist (lockout-risky)
 *   3. PerPortSecurityCard  — Per-port learn-mode + action table
 *   4. IntrusionLogCard     — Intrusion events + reset-flags
 *   5. SslStateCard         — Read-only SSL state summary
 *
 * There is NO card for device passwords. The password-setting operation
 * has no HTTP surface at all (see memory/feedback_switch_write_safety.md).
 */
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
          Manage web-access mode, authorized managers, per-port security, and
          the SSL subsystem. Password changes are intentionally not exposed
          here — run them manually from the legacy applet when needed.
        </p>
      </div>

      <div className="grid gap-4">
        <WebAccessCard />
        <WebManagersCard />
        <PerPortSecurityCard />
        <IntrusionLogCard />
        <SslStateCard />
      </div>
    </div>
  );
}
