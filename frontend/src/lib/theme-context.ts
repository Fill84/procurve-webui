/**
 * Theme context + hook, split from theme.tsx so that file exports only the
 * ThemeProvider component (react-refresh/only-export-components: files that
 * mix component and non-component exports break Fast Refresh).
 */
import { createContext, useContext } from "react";

export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export interface ThemeContextValue {
  /** The user's chosen preference. */
  preference: ThemePreference;
  /** What that preference currently resolves to (system → light/dark). */
  resolved: ResolvedTheme;
  /** Change the preference; persisted immediately. */
  setPreference: (preference: ThemePreference) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
