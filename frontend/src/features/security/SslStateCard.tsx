/**
 * SslStateCard — read-only summary of the SSL subsystem.
 *
 * Three pieces of state, scraped across three HTML pages on the switch:
 *   * ssl_enabled           (power state)
 *   * ssl_port              (listening port)
 *   * cert_mode             (create / use-installed)
 *   * ca_signed_installed   (is a CA-signed cert present?)
 *
 * All configuration of the SSL subsystem happens from the WebAccessCard
 * (which is lockout-risky and goes through the danger dialog). This card
 * exists purely so the operator can see the current state without poking
 * the danger button.
 */
import { useSslState } from "@/api/hooks/useSecurity";

export function SslStateCard() {
  const ssl = useSslState();

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          SSL state (read-only)
        </h4>
        {ssl.isLoading && (
          <span className="text-xs text-neutral-500">Loading…</span>
        )}
      </div>

      {ssl.error instanceof Error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          Failed to fetch SSL state: {ssl.error.message}
        </div>
      )}

      {ssl.data && (
        <dl className="grid grid-cols-[12rem,1fr] gap-y-1 text-sm">
          <dt className="text-neutral-500">HTTPS</dt>
          <dd>
            <span
              className={
                ssl.data.ssl_enabled
                  ? "font-semibold text-green-700"
                  : "text-neutral-700"
              }
            >
              {ssl.data.ssl_enabled ? "ON" : "OFF"}
            </span>
          </dd>

          <dt className="text-neutral-500">SSL port</dt>
          <dd className="font-mono">{ssl.data.ssl_port}</dd>

          <dt className="text-neutral-500">Certificate mode</dt>
          <dd>
            {ssl.data.cert_mode === 1
              ? "Create / self-signed"
              : "Use installed"}
          </dd>

          <dt className="text-neutral-500">CA-signed cert installed</dt>
          <dd>
            {ssl.data.ca_signed_installed ? (
              <span className="font-semibold text-green-700">Yes</span>
            ) : (
              <span className="text-neutral-700">No</span>
            )}
          </dd>
        </dl>
      )}
    </section>
  );
}
