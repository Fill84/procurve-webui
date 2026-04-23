import { Link } from "@tanstack/react-router";

/**
 * Shared stub for tabs whose real implementation is deferred to a later
 * phase (Configuration, Security, Diagnostics, Support).
 */
export function ComingLaterPage({ tabName }: { tabName: string }) {
  return (
    <div className="p-6">
      <div className="mx-auto max-w-xl rounded-lg border border-neutral-200 bg-white p-8 text-center shadow-sm">
        <h2 className="text-xl font-semibold text-neutral-900">{tabName}</h2>
        <p className="mt-3 text-sm text-neutral-600">
          This tab is coming in a later phase. Phase 2 ships Identity, Status,
          and Backups as read-only views; {tabName.toLowerCase()} is planned
          for Phase 3+.
        </p>
        <Link
          to="/"
          className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-800 hover:underline"
        >
          ← Back to Identity
        </Link>
      </div>
    </div>
  );
}
