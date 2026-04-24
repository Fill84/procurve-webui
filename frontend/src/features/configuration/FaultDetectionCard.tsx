/**
 * FaultDetectionCard — sensitivity select for the fault-detection policy.
 *
 * The switch reports a single "ffs" integer code (0, 32, 128, 224) which
 * maps to {Never, High, Medium, Low} sensitivity. Not lockout-risky —
 * this is a local telemetry filter — so we save without a host confirm.
 *
 * `dps` (a second injected read-only telemetry value) is displayed as
 * raw metadata when present; its meaning is undocumented.
 */
import { useEffect, useState } from "react";
import {
  useFaultDetection,
  useSetFaultDetection,
  type FaultSensitivity,
  type SetFaultDetectionRequest,
} from "@/api/hooks/useConfiguration";

// Mirror backend FaultSensitivity IntEnum values (0 = Never, 32 = High,
// 128 = Medium, 224 = Low).
const SENS_OPTIONS: { value: FaultSensitivity; label: string }[] = [
  { value: 0, label: "Never" },
  { value: 32, label: "High" },
  { value: 128, label: "Medium" },
  { value: 224, label: "Low" },
];

export function FaultDetectionCard() {
  const query = useFaultDetection();
  const mutation = useSetFaultDetection();

  const [sensitivity, setSensitivity] = useState<FaultSensitivity>(128);
  const [lastResult, setLastResult] = useState<string | null>(null);

  useEffect(() => {
    if (query.data) setSensitivity(query.data.sensitivity);
  }, [query.data]);

  const dirty =
    !!query.data && sensitivity !== query.data.sensitivity;

  const handleSave = () => {
    setLastResult(null);
    mutation.reset();
    const request: SetFaultDetectionRequest = { sensitivity };
    mutation.mutate(
      { request },
      {
        onSuccess: (data) => {
          setLastResult(
            data.ok
              ? "Fault-detection sensitivity saved."
              : "Save accepted without confirmation.",
          );
        },
      },
    );
  };

  const errorMessage =
    mutation.error instanceof Error ? mutation.error.message : null;
  const canSave = !mutation.isPending && dirty;

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Fault detection
        </h4>
        {query.isLoading && (
          <span className="text-xs text-neutral-500">Loading…</span>
        )}
      </div>

      {query.error instanceof Error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-medium">Failed to load fault detection</p>
          <p className="mt-1 break-all">{query.error.message}</p>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="mt-2 rounded-md border border-red-400 bg-white px-3 py-1.5 text-sm font-medium text-red-900 hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      )}

      {query.data && (
        <>
          <div className="grid gap-3">
            <div>
              <label
                htmlFor="fault-sens"
                className="block text-xs font-medium text-neutral-700"
              >
                Sensitivity
              </label>
              <select
                id="fault-sens"
                value={sensitivity}
                onChange={(e) =>
                  setSensitivity(Number(e.target.value) as FaultSensitivity)
                }
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {SENS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {query.data.dps !== null && query.data.dps !== undefined && (
              <p className="text-xs text-neutral-500">
                Telemetry code (dps): <span className="font-mono">{query.data.dps}</span>
              </p>
            )}
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
                  setSensitivity(query.data.sensitivity);
                  setLastResult(null);
                  mutation.reset();
                }}
                className="text-sm text-neutral-500 hover:text-neutral-900 hover:underline"
              >
                Revert
              </button>
            )}
            {lastResult && (
              <span className="text-sm italic text-neutral-700">
                {lastResult}
              </span>
            )}
          </div>

          {errorMessage && (
            <div className="mt-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              <p className="font-semibold">Save failed</p>
              <p className="mt-1 break-all">{errorMessage}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
