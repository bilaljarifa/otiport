import { useEffect, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../theme/ThemeContext";
import { settlePortfolio } from "../lib/portfolioApi";
import { Brand } from "./Brand";
import { buttonClass } from "./buttonStyles";

const NAV_SECTIONS: { label: string; items: { to: string; label: string }[] }[] = [
  {
    label: "Overview",
    items: [
      { to: "/app/dashboard", label: "Dashboard" },
      { to: "/app/markets", label: "Markets" },
      { to: "/app/portfolio", label: "Portfolio" },
      { to: "/app/watchlist", label: "Watchlist" },
    ],
  },
  {
    label: "Trading",
    items: [
      { to: "/app/trading", label: "Trading" },
      { to: "/app/orders", label: "Orders" },
      { to: "/app/transactions", label: "Transactions" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/app/news", label: "News" },
      { to: "/app/analytics", label: "Analytics" },
      { to: "/app/assistant", label: "AI Assistant" },
    ],
  },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const queryClient = useQueryClient();

  // Open LIMIT orders and active alerts only ever progress when something
  // matches them against a fresh price (see `backend/crud.py::settle`) — the
  // Streamlit app called this once per page render; here there is no
  // equivalent per-render hook, so it runs once on entering the app and then
  // on a fixed interval for as long as an authenticated page is mounted.
  useEffect(() => {
    let cancelled = false;
    async function run() {
      try {
        await settlePortfolio();
      } catch {
        // Best effort — a failed settle must never block the UI; the next
        // tick (or the next order placement) tries again.
      }
      if (!cancelled) void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
    }
    void run();
    const id = setInterval(run, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [queryClient]);

  async function handleLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  return (
    <div className="flex min-h-screen bg-surface">
      <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-surface text-ink">
        <div className="px-4 py-4">
          <Brand size="sm" />
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-2">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label} className="mb-4">
              <div className="px-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-widest text-ink-faint">
                {section.label}
              </div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `block rounded px-2.5 py-1.5 text-sm font-medium ${
                      isActive
                        ? "bg-accent-soft text-ink"
                        : "text-ink-muted hover:bg-surface-alt hover:text-ink"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
          {user?.role === "admin" && (
            <div className="mb-4">
              <div className="px-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-widest text-ink-faint">
                Administration
              </div>
              <NavLink
                to="/app/admin"
                className={({ isActive }) =>
                  `block rounded px-2.5 py-1.5 text-sm font-medium ${
                    isActive
                      ? "bg-accent-soft text-ink"
                      : "text-ink-muted hover:bg-surface-alt hover:text-ink"
                  }`
                }
              >
                Admin
              </NavLink>
            </div>
          )}
        </nav>
        <div className="border-t border-line px-4 py-3">
          <NavLink
            to="/app/settings"
            className="block truncate text-sm font-semibold text-ink hover:text-accent"
          >
            {/* `user` is briefly/indefinitely null on a restored session the
                backend hasn't confirmed yet (offline, or still checking) —
                an empty link and a bare "@" would look like a broken
                profile instead of an app that's just waiting on data. */}
            {user?.full_name ?? "Account"}
          </NavLink>
          {user?.username && <p className="truncate text-xs text-ink-faint">@{user.username}</p>}
        </div>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface/95 px-6 py-3 backdrop-blur">
          <span className="rounded-full border border-line-strong bg-surface-alt px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-ink-muted">
            Paper Trading
          </span>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={toggleTheme}
              className="rounded border border-line-strong px-2.5 py-1.5 text-xs font-semibold text-ink-muted hover:border-ink hover:text-ink"
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? "Dark" : "Light"}
            </button>
            <NavLink to="/app/profile" className="text-sm font-medium text-ink-muted hover:text-ink">
              Profile
            </NavLink>
            <button onClick={handleLogout} className={buttonClass("secondary", "px-3 py-1.5")}>
              Log out
            </button>
          </div>
        </header>
        <main className="flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
