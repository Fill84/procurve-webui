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
              className="h-32 animate-pulse rounded-lg border border-neutral-200 bg-neutral-100"
            />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-900">
          <p className="font-medium">Failed to load support info</p>
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
                Support
              </h3>
              <p className="text-sm text-neutral-600">
                HPE Networking replaces the legacy ProCurve support portal.
              </p>
            </div>
          </Card>

          {/* Links */}
          <Card title="Support links">
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-[max-content_1fr]">
              <div className="contents">
                <dt className="text-sm text-neutral-500">Current portal</dt>
                <dd className="text-sm">
                  <a
                    href={data.current_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="font-mono text-blue-700 underline hover:text-blue-900 break-all"
                  >
                    {data.current_url}
                  </a>
                </dd>
              </div>
              <div className="contents">
                <dt className="text-sm text-neutral-500">Legacy URL</dt>
                <dd className="text-sm">
                  <span
                    className="font-mono text-neutral-500 line-through break-all"
                    title="No longer resolves"
                  >
                    {data.legacy_url}
                  </span>
                  <span className="ml-2 inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                    defunct
                  </span>
                </dd>
              </div>
            </dl>
            <p className="mt-4 rounded-md border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-700">
              {data.note}
            </p>
          </Card>

          {/* Switch identifiers — handy when opening a support case. */}
          <Card title="This switch">
            {identity.isLoading && (
              <p className="text-sm text-neutral-500">Loading identifiers…</p>
            )}
            {identity.isError && (
              <p className="text-sm text-red-700">
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
          <dt className="text-sm text-neutral-500">Model</dt>
          <dd className="text-sm font-mono text-neutral-900 break-all">
            {product}
          </dd>
        </div>
        <div className="contents">
          <dt className="text-sm text-neutral-500">Serial number</dt>
          <dd className="text-sm font-mono text-neutral-900 break-all">
            {serial}
          </dd>
        </div>
      </dl>
      <div>
        <button
          type="button"
          onClick={copy}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
        >
          {copied ? "Copied!" : "Copy model + serial"}
        </button>
      </div>
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
