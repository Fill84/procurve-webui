/**
 * Theme preference: three states, matching what most OSes/browsers offer.
 *
 *   "system" — follow the OS `prefers-color-scheme`, live (default).
 *   "light" / "dark" — an explicit override that sticks across reloads.
 *
 * The preference is persisted to localStorage. Picking "system" *removes*
 * the key so the app genuinely falls back to the OS again (and keeps
 * tracking it if the OS setting later changes).
 *
 * An inline script in index.html applies the resolved theme before React
 * mounts to avoid a flash of the wrong theme; this provider takes over
 * once mounted and keeps the <html> class in sync.
 *
 * The OS `prefers-color-scheme` value is consumed via useSyncExternalStore
 * (matchMedia IS an external store) — the previous
 * "setState inside the subscribe effect" shape both violated the
 * react-hooks lint rule and could paint one frame with a stale resolve.
 *
 * The context + useTheme hook live in theme-context.ts so this file only
 * exports a component (Fast Refresh requirement).
 */
import {
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import {
  ThemeContext,
  type ResolvedTheme,
  type ThemePreference,
} from "./theme-context";

const STORAGE_KEY = "procurve-theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function readStoredPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "system") {
      return value;
    }
  } catch {
    // localStorage can throw in locked-down/private contexts — treat as default.
  }
  return "system";
}

function systemPrefersDark(): boolean {
  return window.matchMedia(DARK_QUERY).matches;
}

function subscribeToSystemTheme(onChange: () => void): () => void {
  const mq = window.matchMedia(DARK_QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

function applyResolvedTheme(resolved: ResolvedTheme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  // Hints native form controls / scrollbars to render in the right scheme.
  root.style.colorScheme = resolved;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(
    readStoredPreference,
  );
  const systemDark = useSyncExternalStore(
    subscribeToSystemTheme,
    systemPrefersDark,
  );
  const resolved: ResolvedTheme =
    preference === "system" ? (systemDark ? "dark" : "light") : preference;

  // The only genuine side effect: mirror the resolved theme onto <html>.
  useEffect(() => {
    applyResolvedTheme(resolved);
  }, [resolved]);

  const setPreference = (next: ThemePreference) => {
    try {
      if (next === "system") {
        localStorage.removeItem(STORAGE_KEY);
      } else {
        localStorage.setItem(STORAGE_KEY, next);
      }
    } catch {
      // Non-fatal: preference just won't persist across reloads.
    }
    setPreferenceState(next);
  };

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference }}>
      {children}
    </ThemeContext.Provider>
  );
}
