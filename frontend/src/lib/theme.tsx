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
 */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type ThemePreference = "system" | "light" | "dark";
type ResolvedTheme = "light" | "dark";

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

function resolvePreference(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") {
    return systemPrefersDark() ? "dark" : "light";
  }
  return preference;
}

function applyResolvedTheme(resolved: ResolvedTheme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  // Hints native form controls / scrollbars to render in the right scheme.
  root.style.colorScheme = resolved;
}

interface ThemeContextValue {
  /** The user's chosen preference. */
  preference: ThemePreference;
  /** What that preference currently resolves to (system → light/dark). */
  resolved: ResolvedTheme;
  /** Change the preference; persisted immediately. */
  setPreference: (preference: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(
    readStoredPreference,
  );
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    resolvePreference(preference),
  );

  // Apply the current preference and, while in "system" mode, keep following
  // the OS if it changes underneath us.
  useEffect(() => {
    const next = resolvePreference(preference);
    setResolved(next);
    applyResolvedTheme(next);

    if (preference !== "system") return;

    const mq = window.matchMedia(DARK_QUERY);
    const onChange = () => {
      const systemResolved: ResolvedTheme = mq.matches ? "dark" : "light";
      setResolved(systemResolved);
      applyResolvedTheme(systemResolved);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [preference]);

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

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
