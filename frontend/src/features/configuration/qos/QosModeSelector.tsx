/**
 * QosModeSelector — the master switch for the QoS family of tables.
 *
 * CosTosMode determines how the switch reads priority fields on the wire:
 *   1 (Disabled)       — QoS off.
 *   2 (IP Precedence)  — 802.1p + CoS-app / user / VLAN tables drive forwarding.
 *   3 (DiffServ)       — DSCP / diffserv tables drive forwarding; CoS tables
 *                        mostly become informational.
 *
 * The backend does not expose a dedicated read endpoint for the current
 * mode (the 2810's applet infers it from priority labels rendered in each
 * sub-table). So this selector keeps its state locally in the parent
 * (`QosSection`). When the user clicks "Apply", we PUT `/qos/mode` and
 * then the parent rerenders the visible sub-tables accordingly.
 *
 * Not lockout-risky — QoS is forwarding-plane, not management-plane.
 */
import { useState } from "react";
import {
  useSetQosMode,
  type CosTosMode,
  type SetCosTosModeRequest,
} from "@/api/hooks/useConfiguration";

const MODE_OPTIONS: { value: CosTosMode; label: string; hint: string }[] = [
  { value: 1, label: "Disabled", hint: "QoS off; all traffic best-effort." },
  {
    value: 2,
    label: "IP Precedence / 802.1p",
    hint: "CoS-app / user / VLAN tables drive forwarding.",
  },
  {
    value: 3,
    label: "DiffServ (DSCP)",
    hint: "DSCP map + DiffServ policy table drive forwarding.",
  },
];

export interface QosModeSelectorProps {
  mode: CosTosMode;
  onModeChange: (mode: CosTosMode) => void;
}

export function QosModeSelector({ mode, onModeChange }: QosModeSelectorProps) {
  const mutation = useSetQosMode();
  const [pending, setPending] = useState<CosTosMode>(mode);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const dirty = pending !== mode;

  const handleApply = () => {
    setLastResult(null);
    mutation.reset();
    const request: SetCosTosModeRequest = { mode: pending };
    mutation.mutate(
      { request },
      {
        onSuccess: (data) => {
          setLastResult(
            data.ok
              ? "QoS mode saved."
              : "Save accepted without confirmation.",
          );
          onModeChange(pending);
        },
      },
    );
  };

  const errorMessage =
    mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          QoS master mode
        </h4>
      </div>

      <p className="mb-3 text-xs text-muted-foreground">
        The 2810 firmware does not expose the current mode as a read — the
        selection below controls both which sub-tables are visible and what
        the switch applies to inbound traffic. If unsure, pick the mode you
        plan to use, apply it, and the sub-cards will update.
      </p>

      <div className="grid gap-2">
        {MODE_OPTIONS.map((opt) => (
          <label
            key={opt.value}
            className={
              "flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2 text-sm " +
              (pending === opt.value
                ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40"
                : "border-border bg-card hover:bg-muted")
            }
          >
            <input
              type="radio"
              name="qos-mode"
              value={opt.value}
              checked={pending === opt.value}
              onChange={() => setPending(opt.value)}
              className="mt-0.5 h-4 w-4 text-blue-600 focus:ring-blue-500"
            />
            <span className="flex-1">
              <span className="block font-medium text-foreground">
                {opt.label}
              </span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                {opt.hint}
              </span>
            </span>
          </label>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={handleApply}
          disabled={!dirty || mutation.isPending}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
        >
          {mutation.isPending ? "Applying…" : "Apply"}
        </button>
        {dirty && !mutation.isPending && (
          <button
            type="button"
            onClick={() => {
              setPending(mode);
              setLastResult(null);
              mutation.reset();
            }}
            className="text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            Revert
          </button>
        )}
        {lastResult && (
          <span className="text-sm italic text-foreground">{lastResult}</span>
        )}
      </div>

      {errorMessage && (
        <div className="mt-3 rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
          <p className="font-semibold">Apply failed</p>
          <p className="mt-1 break-all">{errorMessage}</p>
        </div>
      )}
    </section>
  );
}
