import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "optiport_theme";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

/**
 * Single source of truth for the authenticated app's light/dark preference.
 * Lives above the router (see main.tsx) so any component — not just
 * AppShell, which used to own this as local state — can react to a toggle.
 * That matters for CandlestickChart: it reads CSS custom properties once at
 * chart-creation time, so it needs `theme` in its own effect's dependency
 * array to redraw when the user flips the switch mid-session.
 *
 * The Landing page still pins itself to light via `.theme-light-forced` (see
 * index.css) regardless of this preference — a marketing surface's identity
 * shouldn't shift with a signed-out visitor's OS setting. Login/Register/the
 * Google callback page, however, read this like any other page: they are a
 * real part of the product, and `index.html` carries a small blocking
 * inline script that mirrors the logic below to set `data-theme` before
 * first paint, so there is no flash of the wrong theme on any of them.
 */
function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function initialTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return systemPrefersDark() ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((current) => (current === "light" ? "dark" : "light"));
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
