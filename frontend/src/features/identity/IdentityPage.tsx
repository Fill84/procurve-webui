/**
 * Read-only Identity view.
 *
 * Mirrors the fields exposed by the backend `DeviceIdentity` model — hostname,
 * product string, serial/MAC/firmware, runtime stats, and SNMP contact/location.
 * No write actions on this page in Phase 2.
 *
 * The original Task 2.10 spec also listed `system_description` and
 * `system_clock`; neither exists in the parsed model, so we render `product`
 * as the system description and omit the clock row entirely. See the Task
 * 2.10 context note in the implementation plan for the field audit.
 */
import type { ReactNode } from "react";
import { useIdentity } from "@/api/hooks/useIdentity";
import { formatBytes, formatUptime } from "@/lib/format";

export function IdentityPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useIdentity();

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Identity</h2>
        {data && (
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            {isFetching ? "Refreshing…" : "Refresh"}
          </button>
        )}
      </div>

      {isLoading && (
        <div className="grid gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-lg border border-neutral-200 bg-neutral-100"
            />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
          <p className="font-medium">Failed to load identity</p>
          <p className="mt-1 text-sm opacity-80">
            {error instanceof Error ? error.message : String(error)}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 rounded-md border border-red-400 bg-white px-3 py-1.5 text-sm font-medium text-red-900 hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      )}

      {data && (
        <div className="grid gap-4">
          {/* Hero */}
          <Card>
            <div className="flex flex-col gap-1">
              <h3 className="text-2xl font-semibold text-neutral-900">
                {data.system_name || "(unnamed switch)"}
              </h3>
              <p className="text-sm text-neutral-600">{data.product}</p>
            </div>
          </Card>

          {/* System info */}
          <Card title="System">
            <KeyValueGrid
              rows={[
                ["Serial number", data.serial_number],
                ["Base MAC", data.base_mac],
                ["Firmware", data.firmware_version],
                ["IP address", data.ip_address],
                [
                  "Management server URL",
                  data.management_server_url ? (
                    <a
                      href={data.management_server_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-blue-700 underline hover:text-blue-900"
                    >
                      {data.management_server_url}
                    </a>
                  ) : (
                    <span className="text-neutral-400">—</span>
                  ),
                ],
              ]}
            />
          </Card>

          {/* Runtime */}
          <Card title="Runtime">
            <KeyValueGrid
              rows={[
                ["Uptime", formatUptime(data.uptime_centiseconds)],
                ["CPU", `${data.cpu_pct}%`],
                [
                  "Memory",
                  `${formatBytes(
                    Math.max(0, data.memory_total_bytes - data.memory_free_bytes),
                  )} / ${formatBytes(data.memory_total_bytes)}`,
                ],
              ]}
            />
          </Card>

          {/* Contact */}
          <Card title="Contact">
            <KeyValueGrid
              rows={[
                [
                  "System contact",
                  data.system_contact || (
                    <span className="text-neutral-400">—</span>
                  ),
                ],
                [
                  "System location",
                  data.system_location || (
                    <span className="text-neutral-400">—</span>
                  ),
                ],
              ]}
            />
          </Card>
        </div>
      )}
    </div>
  );
}

function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      {title && (
        <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          {title}
        </h4>
      )}
      {children}
    </section>
  );
}

function KeyValueGrid({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-[max-content_1fr]">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-sm text-neutral-500">{label}</dt>
          <dd className="text-sm font-mono text-neutral-900 break-all">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
