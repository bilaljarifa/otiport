import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

/**
 * Client-side convenience only — redirects an unauthenticated visitor to
 * the landing page instead of flashing a protected screen. This is *not*
 * the actual security boundary: every backend endpoint independently
 * rejects an absent/invalid/expired/revoked token regardless of what the
 * React router does (see `backend/deps.py`). A stale/cleared token here
 * simply can't fetch real data — there's nothing to "stay logged into".
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-ink-muted">
        Loading…
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
