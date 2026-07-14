/**
 * Configuration-report card.
 *
 * The user presses "Generate" to trigger the GET (the query is `enabled:false`
 * by default so we don't hammer the switch on navigation). We then render the
 * scraped running-config text in a monospaced <pre> with Download and Copy
 * affordances. Download synthesises an `<a download>` click for a .txt blob.
 */
import { useState } from "react";
import { useConfigurationReport } from "@/api/hooks/useDiagnostics";

export function ConfigReportCard() {
  const report = useConfigurationReport();
  const [copied, setCopied] = useState(false);

  const configText = report.data?.config_text ?? "";

  const handleDownload = () => {
    const blob = new Blob([configText], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "running-config.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(configText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can fail in insecure contexts — stay silent; the user can
      // always use Download as a fallback.
    }
  };

  const errorMessage =
    report.error instanceof Error ? report.error.message : null;

  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Configuration report
        </h4>
        <div className="flex items-center gap-2">
          {report.data != null && (
            <>
              <button
                type="button"
                onClick={handleCopy}
                className="rounded-md border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted"
              >
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                onClick={handleDownload}
                className="rounded-md border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted"
              >
                Download .txt
              </button>
            </>
          )}
          <button
            type="button"
            onClick={() => {
              void report.refetch();
            }}
            disabled={report.isFetching}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:bg-blue-300"
          >
            {report.isFetching
              ? "Generating…"
              : report.data
                ? "Refresh"
                : "Generate"}
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="rounded-md border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-3 text-sm text-red-900 dark:text-red-300">
          <p className="font-semibold">Failed to fetch configuration report</p>
          <p className="mt-1 break-all">{errorMessage}</p>
        </div>
      )}

      {!report.data && !errorMessage && !report.isFetching && (
        <p className="text-sm text-muted-foreground">
          Press <span className="font-medium">Generate</span> to fetch the
          current running-config.
        </p>
      )}

      {report.data && (
        <pre className="max-h-96 overflow-auto rounded border border-border bg-muted p-3 text-xs leading-5">
          <code className="block whitespace-pre font-mono text-foreground">
            {configText}
          </code>
        </pre>
      )}
    </section>
  );
}
