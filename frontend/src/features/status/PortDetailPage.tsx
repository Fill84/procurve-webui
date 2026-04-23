/**
 * Placeholder per-port detail page. Task 2.12 replaces this with counters,
 * live stats, and the historical chart.
 */
export function PortDetailPage({ port }: { port: string }) {
  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold">Port {port}</h2>
      <p className="mt-2 text-sm text-neutral-600">
        Port detail placeholder — real implementation arrives in Task 2.12.
      </p>
    </div>
  );
}
