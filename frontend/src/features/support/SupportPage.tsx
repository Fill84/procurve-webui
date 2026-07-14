/**
 * Read-only Support view.
 *
 * The legacy 2810 Support tab was a static HTML redirect to
 * http://www.procurve.com, which no longer resolves. The backend's
 * `/api/v1/support` endpoint returns canonical replacement info (HPE
 * Networking portal) along with a parity note. We pair that info with the
 * current switch's model/serial (from `useIdentity`) to give the user
 * everything they'd need to open a support case: the right URL plus the
 * identifiers HPE will ask for.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { useIdentity } from "@/api/hooks/useIdentity";
import { useSupport } from "@/api/hooks/useSupport";

export function SupportPage() {
  const { data, isLoading, isError, error, refetch } = useSupport();
  const identity = useIdentity();

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Support</h2>
      </div>

      {isLoading && (
        <div className="grid gap-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-lg border border-border bg-muted"
            />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-4 text-red-900 dark:text-red-300">
          <p className="font-medium">Failed to load support info</p>
          <p className="mt-1 text-sm opacity-80">
            {error instanceof Error ? error.message : String(error)}
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
                Support
              </h3>
              <p className="text-sm text-muted-foreground">
                HPE Networking replaces the legacy ProCurve support portal.
              </p>
            </div>
          </Card>

          {/* Links */}
          <Card title="Support links">
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-[max-content_1fr]">
              <div className="contents">
                <dt className="text-sm text-muted-foreground">Current portal</dt>
                <dd className="text-sm">
                  <a
                    href={data.current_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="font-mono text-blue-700 dark:text-blue-300 underline hover:text-blue-900 break-all"
                  >
                    {data.current_url}
                  </a>
                </dd>
              </div>
              <div className="contents">
                <dt className="text-sm text-muted-foreground">Legacy URL</dt>
                <dd className="text-sm">
                  <span
                    className="font-mono text-muted-foreground line-through break-all"
                    title="No longer resolves"
                  >
                    {data.legacy_url}
                  </span>
                  <span className="ml-2 inline-flex items-center rounded-full bg-amber-100 dark:bg-amber-900/40 px-2 py-0.5 text-xs font-medium text-amber-900 dark:text-amber-300">
                    defunct
                  </span>
                </dd>
              </div>
              <div className="contents">
                <dt className="text-sm text-muted-foreground">Project repo</dt>
                <dd className="text-sm">
                  <a
                    href="https://github.com/Fill84/procurve-webui"
                    target="_blank"
                    rel="noreferrer noopener"
                    className="font-mono text-blue-700 dark:text-blue-300 underline hover:text-blue-900 break-all"
                  >
                    github.com/Fill84/procurve-webui
                  </a>
                  <span className="ml-2 text-xs text-muted-foreground">
                    source &amp; contributions
                  </span>
                </dd>
              </div>
              <div className="contents">
                <dt className="text-sm text-muted-foreground">Report an issue</dt>
                <dd className="text-sm">
                  <a
                    href="https://github.com/Fill84/procurve-webui/issues/new"
                    target="_blank"
                    rel="noreferrer noopener"
                    className="font-mono text-blue-700 dark:text-blue-300 underline hover:text-blue-900 break-all"
                  >
                    github.com/Fill84/procurve-webui/issues/new
                  </a>
                  <span className="ml-2 text-xs text-muted-foreground">
                    bug reports &amp; feature requests
                  </span>
                </dd>
              </div>
            </dl>
            <p className="mt-4 rounded-md border border-border bg-muted p-3 text-xs text-foreground">
              {data.note}
            </p>
          </Card>

          {/* Switch identifiers — handy when opening a support case. */}
          <Card title="This switch">
            {identity.isLoading && (
              <p className="text-sm text-muted-foreground">Loading identifiers…</p>
            )}
            {identity.isError && (
              <p className="text-sm text-red-700 dark:text-red-300">
                Could not load switch identity.
              </p>
            )}
            {identity.data && (
              <SwitchIdentifiers
                product={identity.data.product}
                serial={identity.data.serial_number}
              />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

function SwitchIdentifiers({
  product,
  serial,
}: {
  product: string;
  serial: string;
}) {
  const [copied, setCopied] = useState(false);
  const combo = `${product} — Serial ${serial}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(combo);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can fail in insecure contexts; silently ignore.
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-[max-content_1fr]">
        <div className="contents">
          <dt className="text-sm text-muted-foreground">Model</dt>
          <dd className="text-sm font-mono text-foreground break-all">
            {product}
          </dd>
        </div>
        <div className="contents">
          <dt className="text-sm text-muted-foreground">Serial number</dt>
          <dd className="text-sm font-mono text-foreground break-all">
            {serial}
          </dd>
        </div>
      </dl>
      <div>
        <button
          type="button"
          onClick={copy}
          className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
        >
          {copied ? "Copied!" : "Copy model + serial"}
        </button>
      </div>
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
