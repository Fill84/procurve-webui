/**
 * DeviceFeaturesCard — toggle IGMP snooping and Spanning Tree.
 *
 * Not lockout-risky: turning STP / IGMP on or off keeps the management
 * session alive. Pre-write autobackup on the backend is sufficient
 * rollback, so we don't prompt for host confirmation.
 *
 * VLAN count is read-only (it's scraped from the features page as a
 * sanity indicator; the applet uses it to pick which of the five
 * feature-set endpoints to PUT to, but the single-VLAN deployment this
 * switch runs today always uses `/cgi/feature_set`).
 */
import { apiErrorMessage } from "@/api/client";
import { useState } from "react";
import { useServerSync } from "@/lib/useServerSync";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import {
  useDeviceFeatures,
  useSetDeviceFeatures,
  type SetDeviceFeaturesRequest,
} from "@/api/hooks/useConfiguration";

export function DeviceFeaturesCard() {
  const query = useDeviceFeatures();
  const mutation = useSetDeviceFeatures();

  const [igmp, setIgmp] = useState(false);
  const [stp, setStp] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  useServerSync(query.data, (data) => {
    // Default to False when the switch returned null ("Invalid OID"
    // sentinel on multi-VLAN variants) so the UI shows a deterministic
    // checkbox state.
    setIgmp(data.igmp ?? false);
    setStp(data.spanning_tree ?? false);
  });

  const dirty =
    !!query.data &&
    (igmp !== (query.data.igmp ?? false) ||
      stp !== (query.data.spanning_tree ?? false));

  const handleSave = () => {
    setLastResult(null);
    mutation.reset();
    const request: SetDeviceFeaturesRequest = {
      endpoint: "/cgi/feature_set",
      vlan_id: 1,
      igmp,
      spanning_tree: stp,
    };
    mutation.mutate(
      { request },
      {
        onSuccess: (data) => {
          setLastResult(
            data.ok
              ? "Device features saved."
              : "Save accepted without confirmation.",
          );
        },
      },
    );
  };

  const errorMessage =
    apiErrorMessage(mutation.error);
  const canSave = !mutation.isPending && dirty;

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Device features
        </h4>
        {query.isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <ErrorBanner>
          <p className="font-medium">Failed to load device features</p>
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
          <dl className="mb-4 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 text-sm">
            <dt className="text-muted-foreground">VLAN count</dt>
            <dd className="font-mono text-foreground">
              {query.data.vlan_count}
            </dd>
          </dl>

          <div className="grid gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={igmp}
                onChange={(e) => setIgmp(e.target.checked)}
                className="h-4 w-4 rounded border-border text-blue-600 focus:ring-blue-500"
              />
              <span className="font-medium text-foreground">IGMP snooping</span>
              {query.data.igmp === null && (
                <span className="text-xs text-muted-foreground">
                  (not reported by switch)
                </span>
              )}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={stp}
                onChange={(e) => setStp(e.target.checked)}
                className="h-4 w-4 rounded border-border text-blue-600 focus:ring-blue-500"
              />
              <span className="font-medium text-foreground">
                Spanning Tree
              </span>
              {query.data.spanning_tree === null && (
                <span className="text-xs text-muted-foreground">
                  (not reported by switch)
                </span>
              )}
            </label>
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
                  setIgmp(query.data.igmp ?? false);
                  setStp(query.data.spanning_tree ?? false);
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
