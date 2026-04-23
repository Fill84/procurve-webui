/**
 * Shared stub for tabs whose real implementation is deferred to a later
 * phase (Configuration, Security, Diagnostics, Support). Task 2.14 may
 * polish this; the stub is sufficient for routing.
 */
export function ComingLaterPage({ tabName }: { tabName: string }) {
  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold">{tabName}</h2>
      <p className="mt-2 text-sm text-neutral-600">
        This tab is coming in a later phase.
      </p>
    </div>
  );
}
