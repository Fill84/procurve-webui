/**
 * IntrusionLogCard — list of intrusion entries + Reset-flags button.
 *
 * Reset only clears cosmetic alert flags (it does NOT wipe the log). Not
 * lockout-risky, so no DangerConfirmDialog — but the mutation still goes
 * through the backend autobackup wrapper, and on success we invalidate
 * the intrusion query so the cleared flags are reflected in the UI.
 */
import { useIntrusion, useResetIntrusion } from "@/api/hooks/useSecurity";

export function IntrusionLogCard() {
  const intrusion = useIntrusion();
  const reset = useResetIntrusion();

  const entries = intrusion.data?.entries ?? [];
  const errorMessage =
    reset.error instanceof Error ? reset.error.message : null;

  const handleReset = () => {
    reset.mutate();
  };

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Intrusion log
        </h4>
        <button
          type="button"
          onClick={handleReset}
          disabled={reset.isPending}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground shadow-sm hover:bg-muted disabled:opacity-50"
        >
          {reset.isPending ? "Resetting…" : "Reset flags"}
        </button>
      </div>

      {intrusion.error instanceof Error && (
        <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          Failed to fetch intrusion log: {intrusion.error.message}
        </div>
      )}

      {errorMessage && (
        <div className="mb-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          <p className="font-semibold">Reset failed</p>
          <p className="mt-1 break-all">{errorMessage}</p>
        </div>
      )}

      {reset.isSuccess && !errorMessage && (
        <p className="mb-3 text-sm italic text-foreground">
          Intrusion flags cleared.
        </p>
      )}

      <div className="overflow-x-auto rounded border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left">Port</th>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Intruder</th>
              <th className="px-3 py-2 text-left">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {entries.length === 0 && !intrusion.isLoading && (
              <tr>
                <td
                  colSpan={4}
                  className="px-3 py-3 text-center text-muted-foreground"
                >
                  No intrusion events recorded.
                </td>
              </tr>
            )}
            {entries.map((entry, idx) => (
              <tr key={`${entry.port}-${entry.timestamp}-${idx}`}>
                <td className="px-3 py-2 font-mono">{entry.port}</td>
                <td className="px-3 py-2">
                  {entry.port_name.trim() || "—"}
                </td>
                <td className="px-3 py-2 font-mono">
                  {entry.intruder_address}
                </td>
                <td className="px-3 py-2 font-mono">{entry.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
