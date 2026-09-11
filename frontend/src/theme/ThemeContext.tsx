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
 * Public pages (Landing/Login/Register) intentionally never read this — they
 * pin themselves to light via the `.theme-light-forced` CSS class instead
 * (see index.css), so this preference cannot leak into the marketing site
 * via a client-side navigation that never unmounts <html>.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(STORAGE_KEY) as Theme) || "light",
  );

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
