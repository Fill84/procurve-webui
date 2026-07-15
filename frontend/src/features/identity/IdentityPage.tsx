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
import { apiErrorMessage } from "@/api/client";
import type { ReactNode } from "react";
import { useIdentity } from "@/api/hooks/useIdentity";
import { formatBytes, formatUptime } from "@/lib/format";
import { useLiveUptime } from "@/lib/utils";

export function IdentityPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useIdentity();
  const liveUptime = useLiveUptime(
    formatUptime,
    data?.uptime_centiseconds ?? 0,
  );

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Identity</h2>
        {data && (
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
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
              className="h-32 animate-pulse rounded-lg border border-border bg-muted"
            />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-4 text-red-900 dark:text-red-300">
          <p className="font-medium">Failed to load identity</p>
          <p className="mt-1 text-sm opacity-80">
            {apiErrorMessage(error)}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 rounded-md border border-red-400 dark:border-red-900 bg-card px-3 py-1.5 text-sm font-medium text-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
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
              <h3 className="text-2xl font-semibold text-foreground">
                {data.system_name || "(unnamed switch)"}
              </h3>
              <p className="text-sm text-muted-foreground">{data.product}</p>
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
                      className="text-blue-700 dark:text-blue-300 underline hover:text-blue-900"
                    >
                      {data.management_server_url}
                    </a>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  ),
                ],
              ]}
            />
          </Card>

          {/* Runtime */}
          <Card title="Runtime">
            <KeyValueGrid
              rows={[
                ["Uptime", liveUptime],
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
                    <span className="text-muted-foreground">—</span>
                  ),
                ],
                [
                  "System location",
                  data.system_location || (
                    <span className="text-muted-foreground">—</span>
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
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      {title && (
        <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
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
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className="text-sm font-mono text-foreground break-all">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
