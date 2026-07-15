import { type ClassValue, clsx } from "clsx";
import { useState, useSyncExternalStore } from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

function subscribeEverySecond(onTick: () => void): () => void {
  const id = setInterval(onTick, 1000);
  return () => clearInterval(id);
}

function getNowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

interface UptimeAnchor {
  /** Switch-reported uptime at the moment it arrived. */
  startCentiseconds: number;
  /** Wall-clock second when it arrived. */
  anchoredAtSeconds: number;
}

/**
 * Live uptime display derived from the switch-reported uptime.
 *
 * The wall clock is consumed as an external store (useSyncExternalStore,
 * quantized to whole seconds) and the reported uptime is anchored to it the
 * moment it arrives; each tick recomputes elapsed time from the clock.
 * Three properties fall out of that design:
 *
 * - **No drift under timer throttling.** Background tabs throttle timers to
 *   >=1 s; the previous fixed `+10 centiseconds per 100 ms fire`
 *   accumulator fell ~54 minutes behind per hidden hour. Wall-clock
 *   arithmetic is immune — a late tick just computes a larger delta.
 * - **One re-render per second** instead of ten: the display only changes
 *   visibly once per second, so ticking faster was pure CPU burn on pages
 *   (Status dashboard) that are left open all day.
 * - **Render-pure**: no `Date.now()` in the render body (react-hooks/purity).
 */
export function useLiveUptime(
  formatter: (uptime: number) => string,
  startTimeCentiseconds?: number,
): string {
  const nowSeconds = useSyncExternalStore(subscribeEverySecond, getNowSeconds);

  // Re-anchor during render whenever a fresh uptime arrives (identity
  // refetch) — derived-state pattern, no effect involved.
  const [anchor, setAnchor] = useState<UptimeAnchor | null>(null);
  if (anchor?.startCentiseconds !== startTimeCentiseconds) {
    setAnchor(
      startTimeCentiseconds === undefined
        ? null
        : {
            startCentiseconds: startTimeCentiseconds,
            anchoredAtSeconds: nowSeconds,
          },
    );
  }

  const current =
    anchor === null
      ? 0
      : anchor.startCentiseconds +
        (nowSeconds - anchor.anchoredAtSeconds) * 100;
  return formatter(current);
}
