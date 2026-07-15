/**
 * ErrorBanner — the single red error banner used across every feature.
 *
 * Extracted from ~43 copy-pasted instances (audit M17). Keep the palette in
 * sync with the danger styling in DangerConfirmDialog if it ever changes.
 */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ErrorBannerProps {
  /** Optional bold first line, e.g. "Apply failed". */
  title?: string;
  children: ReactNode;
  className?: string;
}

export function ErrorBanner({ title, children, className }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300",
        className,
      )}
    >
      {title && <p className="font-semibold">{title}</p>}
      <div className={cn("break-words", title && "mt-1")}>{children}</div>
    </div>
  );
}
