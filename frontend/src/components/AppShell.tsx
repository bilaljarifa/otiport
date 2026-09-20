import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { settlePortfolio } from "../lib/portfolioApi";
import { Brand } from "./Brand";
import { buttonClass } from "./buttonStyles";
import { ThemeToggle } from "./ThemeToggle";

const NAV_SECTIONS: { label: string; items: { to: string; label: string }[] }[] = [
  {
    label: "Overview",
    items: [
      { to: "/app/dashboard", label: "Dashboard" },
      { to: "/app/markets", label: "Markets" },
      { to: "/app/portfolio", label: "Portfolio" },
      { to: "/app/watchlist", label: "Watchlist" },
      { to: "/app/report", label: "Report" },
      { to: "/app/billing", label: "Billing" },
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
      { to: "/app/risk", label: "Risk Center" },
      { to: "/app/scenario", label: "Scenario Analysis" },
      { to: "/app/assistant", label: "AI Assistant" },
    ],
  },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const closeMobileNav = () => setMobileNavOpen(false);

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
    <div className="app-shell flex min-h-screen overflow-x-hidden bg-surface">
      {/* Backdrop — mobile/tablet only, closes the drawer on tap. Sits below
          the drawer (z-30 vs z-40) and above ordinary page content. */}
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink/40 lg:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 -translate-x-full flex-col border-r border-line bg-surface text-ink transition-transform duration-200 ease-out lg:static lg:z-auto lg:w-56 lg:translate-x-0 ${
          mobileNavOpen ? "translate-x-0" : ""
        }`}
      >
        <div className="flex items-center justify-between px-4 py-4">
          <Brand size="sm" />
          <button
            type="button"
            onClick={() => setMobileNavOpen(false)}
            className="rounded p-1 text-ink-muted hover:text-ink lg:hidden"
            aria-label="Close menu"
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
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
                  onClick={closeMobileNav}
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
            <div className="mb-4 border-t border-line-soft pt-3">
              <div className="px-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-widest text-ink-faint">
                Administration
              </div>
              <NavLink
                to="/app/admin"
                onClick={closeMobileNav}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded px-2.5 py-1.5 text-sm font-medium ${
                    isActive
                      ? "bg-accent-soft text-ink"
                      : "text-ink-muted hover:bg-surface-alt hover:text-ink"
                  }`
                }
              >
                <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5 shrink-0" aria-hidden="true">
                  <path
                    d="M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinejoin="round"
                  />
                </svg>
                Admin
              </NavLink>
            </div>
          )}
        </nav>
        <div className="border-t border-line px-4 py-3">
          <NavLink
            to="/app/settings"
            onClick={closeMobileNav}
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

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-line bg-surface/95 px-4 py-3 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              className="shrink-0 rounded border border-line-strong p-1.5 text-ink-muted hover:border-ink hover:text-ink lg:hidden"
              aria-label="Open menu"
            >
              <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
                <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
            <span className="hidden shrink-0 rounded-full border border-line-strong bg-surface-alt px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-ink-muted sm:inline">
              Paper Trading
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-2 sm:gap-4">
            <ThemeToggle />
            <NavLink
              to="/app/profile"
              className="hidden text-sm font-medium text-ink-muted hover:text-ink sm:inline"
            >
              Profile
            </NavLink>
            <button onClick={handleLogout} className={buttonClass("secondary", "px-2.5 py-1.5 text-xs sm:px-3 sm:text-sm")}>
              Log out
            </button>
          </div>
        </header>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
