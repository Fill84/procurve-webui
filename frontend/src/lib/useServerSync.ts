import { useState } from "react";

/**
 * Seed/refresh local form state from freshly-arrived server data WITHOUT an
 * effect.
 *
 * Runs `sync(data)` during render whenever `data`'s identity changes (and is
 * non-null). Render-phase state updates in the same component are the
 * React-sanctioned "derived state reset" pattern
 * (https://react.dev/learn/you-might-not-need-an-effect
 * #resetting-all-state-when-a-prop-changes): React discards the
 * just-rendered output and re-renders synchronously, so — unlike the old
 * `useEffect(() => setX(...), [query.data])` shape this replaces — the user
 * never sees a paint of stale form state, and there is no cascading
 * post-paint render for the lint rule to flag.
 *
 * `sync` may call multiple setState setters; keep it free of side effects
 * beyond state (it runs during render).
 */
export function useServerSync<T>(
  data: T | null | undefined,
  sync: (data: T) => void,
): void {
  const [last, setLast] = useState<T | null | undefined>(undefined);
  if (data !== last) {
    setLast(data);
    if (data != null) sync(data);
  }
}
