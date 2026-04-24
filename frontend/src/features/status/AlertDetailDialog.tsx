/**
 * Modal showing the parsed contents of a single alert event.
 *
 * The detail comes from `GET /api/v1/status/alerts/{index}?dt=<ts>` which
 * the backend scrapes from the switch's `/cgi/ffdetail` HTML page (see
 * research/protocol/status/get_alert_detail.md). Layout mirrors the legacy
 * applet's popup: header with severity badge + affected port + timestamp,
 * then Description / Solution / Other Possibilities sections.
 *
 * The dialog has no Ack / Delete buttons inside — those live on the
 * overview page so the same selection state drives multi-event actions.
 *
 * UX choices:
 *   * Hand-rolled modal (matches the existing Phase 3 dialog style; no
 *     shadcn Dialog dependency yet).
 *   * Click-outside to close, plus an explicit [Close] button.
 *   * Severity 1..5 mapped to a colour (Critical → blue, per the legacy
 *     `<severity>d.gif` icon convention).
 */
import type { AlertDetail } from "@/api/hooks/useStatus";
import { useAlertDetail } from "@/api/hooks/useStatus";
import { formatAlertTimestamp } from "@/lib/format-alert";

interface AlertDetailDialogProps {
  /** Row id of the event to load. `null` closes the dialog. */
  index: number | null;
  /** ts_centiseconds of the event (integrity token for the switch). */
  tsCenti: number | null;
  /**
   * Current uptime in centiseconds (from useIdentity). Used to render the
   * timestamp as a wall-clock value relative to the browser's clock. May
   * be undefined if identity hasn't loaded yet — formatAlertTimestamp
   * falls back to a relative form.
   */
  currentUptimeCenti: number | undefined;
  onClose: () => void;
}

export function AlertDetailDialog({
  index,
  tsCenti,
  currentUptimeCenti,
  onClose,
}: AlertDetailDialogProps) {
  const open = index !== null && tsCenti !== null;
  const detail = useAlertDetail(index, tsCenti);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white shadow-xl">
        {detail.isLoading && (
          <div className="p-6">
            <div className="h-6 w-1/3 animate-pulse rounded bg-neutral-200" />
            <div className="mt-4 h-32 animate-pulse rounded bg-neutral-100" />
          </div>
        )}
        {detail.isError && (
          <div className="p-6">
            <h3 className="text-lg font-semibold text-red-900">
              Failed to load event details
            </h3>
            <p className="mt-2 text-sm text-red-800">
              {detail.error instanceof Error
                ? detail.error.message
                : String(detail.error)}
            </p>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
              >
                Close
              </button>
            </div>
          </div>
        )}
        {detail.data && (
          <AlertDetailBody
            detail={detail.data}
            currentUptimeCenti={currentUptimeCenti}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}

function AlertDetailBody({
  detail,
  currentUptimeCenti,
  onClose,
}: {
  detail: AlertDetail;
  currentUptimeCenti: number | undefined;
  onClose: () => void;
}) {
  // pydantic emits default_factory=list as schema-optional; the wire always
  // carries the field so this defaults to [] in practice.
  const solution = detail.solution ?? [];
  return (
    <>
      <header className="border-b border-neutral-200 px-6 py-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-semibold text-neutral-900">
            {detail.title}
          </h3>
          <SeverityBadge severity={detail.severity} />
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-neutral-600">
          {detail.affected_port > 0 && (
            <span>
              <span className="font-medium text-neutral-700">Port:</span>{" "}
              <span className="font-mono">{detail.affected_port}</span>
            </span>
          )}
          <span>
            <span className="font-medium text-neutral-700">When:</span>{" "}
            <span className="font-mono text-xs">
              {formatAlertTimestamp(detail.ts_centiseconds, currentUptimeCenti)}
            </span>
          </span>
        </div>
      </header>

      <div className="space-y-4 px-6 py-4 text-sm text-neutral-800">
        {detail.description && (
          <Section title="Description">
            <p>{detail.description}</p>
          </Section>
        )}
        {solution.length > 0 && (
          <Section title="Solution">
            <ul className="list-disc space-y-1 pl-5">
              {solution.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          </Section>
        )}
        {detail.other_possibilities && (
          <Section title="Other Possibilities">
            <p>{detail.other_possibilities}</p>
          </Section>
        )}
        {!detail.description &&
          solution.length === 0 &&
          !detail.other_possibilities && (
            <p className="italic text-neutral-500">
              The switch did not provide additional detail for this event.
            </p>
          )}
      </div>

      <footer className="flex justify-end gap-2 border-t border-neutral-200 px-6 py-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
        >
          Close
        </button>
      </footer>
    </>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {title}
      </h4>
      <div className="text-sm text-neutral-800">{children}</div>
    </section>
  );
}

/**
 * Severity 1..5. Lower = more severe (matches the legacy `<n>d.gif` icon
 * convention where 1 was a red exclamation).
 */
function SeverityBadge({ severity }: { severity: number }) {
  const { label, classes } = severityStyle(severity);
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${classes}`}
    >
      {label}
    </span>
  );
}

function severityStyle(severity: number): {
  label: string;
  classes: string;
} {
  switch (severity) {
    case 1:
      return {
        label: "Sev 1 · Critical",
        classes: "border-red-300 bg-red-50 text-red-800",
      };
    case 2:
      return {
        label: "Sev 2 · Major",
        classes: "border-orange-300 bg-orange-50 text-orange-800",
      };
    case 3:
      return {
        label: "Sev 3 · Warning",
        classes: "border-amber-300 bg-amber-50 text-amber-800",
      };
    case 4:
      return {
        label: "Sev 4 · Info",
        classes: "border-blue-300 bg-blue-50 text-blue-800",
      };
    case 5:
      return {
        label: "Sev 5 · Notice",
        classes: "border-neutral-300 bg-neutral-50 text-neutral-700",
      };
    default:
      return {
        label: `Sev ${severity}`,
        classes: "border-neutral-300 bg-neutral-50 text-neutral-700",
      };
  }
}
