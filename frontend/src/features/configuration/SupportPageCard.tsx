/**
 * SupportPageCard — edit the two URL fields on the applet's Support page.
 *
 * This is the Configuration tab's editable Support-page form, NOT the
 * Phase 3.2 static Support TAB (which is the read-only `SupportInfo`
 * view at `/support`). Two different things:
 *
 *   - Configuration ▸ Support URLs  → this card, edits 2 URL fields
 *   - Support tab                   → static device info, read-only
 *
 * Not lockout-risky: URL strings don't affect management access. No
 * confirmation dialog — the write goes straight through on Save. A
 * pre-write autobackup is still taken server-side, so the operator can
 * roll back from the Backups tab.
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { useServerSync } from "@/lib/useServerSync";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useSetSupportPageConfig,
  useSupportPageConfig,
  type SetSupportRequest,
} from "@/api/hooks/useConfiguration";

// Backend caps each URL at 103 chars (SUPPORT_FIELD_PATTERN + max_length).
const MAX_URL = 103;

export function SupportPageCard() {
  const query = useSupportPageConfig();
  const mutation = useSetSupportPageConfig();

  const [supportUrl, setSupportUrl] = useState("");
  const [mgmtUrl, setMgmtUrl] = useState("");
  const [lastResult, setLastResult] = useState<string | null>(null);

  // Seed local form state from the fetched page the first time it arrives.
  useServerSync(query.data, (data) => {
    setSupportUrl(data.support_url);
    setMgmtUrl(data.mgmt_url);
  });

  const handleSave = () => {
    setLastResult(null);
    mutation.reset();
    const request: SetSupportRequest = {
      support_url: supportUrl,
      mgmt_url: mgmtUrl,
    };
    mutation.mutate(
      { request },
      {
        onSuccess: (data) => {
          setLastResult(
            data.ok
              ? "Support URLs saved."
              : "Save accepted without confirmation.",
          );
        },
      },
    );
  };

  const errorMessage =
    apiErrorMessage(mutation.error);

  const dirty =
    !!query.data &&
    (supportUrl !== query.data.support_url ||
      mgmtUrl !== query.data.mgmt_url);

  const canSave =
    !mutation.isPending &&
    dirty &&
    supportUrl.trim().length > 0 &&
    mgmtUrl.trim().length > 0;

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Support URLs
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        The two URL fields the applet's Support tab shows. Not
        lockout-risky — saved immediately with a pre-write autobackup.
      </p>

      {query.isLoading && (
        <div className="grid gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded border border-border bg-muted"
            />
          ))}
        </div>
      )}

      {query.error instanceof Error && (
        <ErrorBanner>
          <p className="font-medium">Failed to load support URLs</p>
          <p className="mt-1 break-all">{query.error.message}</p>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="mt-2 rounded-md border border-red-400 dark:border-red-900 bg-card px-3 py-1.5 text-sm font-medium text-red-900 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
          >
            Retry
          </button>
        </ErrorBanner>
      )}

      {query.data && (
        <>
          <div className="grid gap-3">
            <div>
              <label
                htmlFor="support-url"
                className="block text-xs font-medium text-foreground"
              >
                Support URL
              </label>
              <input
                id="support-url"
                type="text"
                value={supportUrl}
                maxLength={MAX_URL}
                onChange={(e) => setSupportUrl(e.target.value)}
                className="mt-1 w-full rounded-md border border-border px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label
                htmlFor="mgmt-url"
                className="block text-xs font-medium text-foreground"
              >
                Management server URL
              </label>
              <input
                id="mgmt-url"
                type="text"
                value={mgmtUrl}
                maxLength={MAX_URL}
                onChange={(e) => setMgmtUrl(e.target.value)}
                className="mt-1 w-full rounded-md border border-border px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={!canSave}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {mutation.isPending ? "Saving…" : "Save"}
            </button>
            {dirty && !mutation.isPending && (
              <button
                type="button"
                onClick={() => {
                  if (!query.data) return;
                  setSupportUrl(query.data.support_url);
                  setMgmtUrl(query.data.mgmt_url);
                  setLastResult(null);
                  mutation.reset();
                }}
                className="text-sm text-muted-foreground hover:text-foreground hover:underline"
              >
                Revert
              </button>
            )}
            {lastResult && (
              <span className="text-sm italic text-foreground">
                {lastResult}
              </span>
            )}
          </div>

          {errorMessage && (
            <ErrorBanner title="Save failed" className="mt-3">
              {errorMessage}
            </ErrorBanner>
          )}
        </>
      )}
    </section>
  );
}
