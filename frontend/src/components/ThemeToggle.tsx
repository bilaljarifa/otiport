import { useTheme } from "../theme/ThemeContext";

/** Shared light/dark switcher — used by both the authenticated AppShell
 * header and the public auth pages (Login/Register/Google callback), so
 * there is exactly one toggle implementation and one visual language for
 * "which theme am I in" across the app. */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
      className={`inline-flex items-center gap-1.5 rounded border border-line-strong px-2.5 py-1.5 text-xs font-semibold text-ink-muted transition-colors hover:border-ink hover:text-ink ${className}`}
    >
      <span aria-hidden="true">{isDark ? "☾" : "☀"}</span>
      <span className="hidden sm:inline">{isDark ? "Dark" : "Light"}</span>
    </button>
  );
}
