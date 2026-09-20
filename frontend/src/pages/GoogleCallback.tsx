import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/apiClient";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";

/**
 * Google's own redirect lands on the backend (`GET /auth/google/callback`
 * is the Authorized redirect URI registered on the Google Cloud OAuth
 * client — not this page). That backend route does the actual code
 * exchange and verification, then bounces the browser here with the result:
 *   - success: `#access_token=<jwt>` in the URL fragment (never sent to any
 *     server, including ours — safer than a query parameter for a token)
 *   - failure: `?error=<message>` in the query string
 * This page's only job is to read whichever one is present and either
 * adopt the session or show the error — it never talks to Google directly.
 */
export function GoogleCallbackPage() {
  const [searchParams] = useSearchParams();
  const { completeGoogleRedirect } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const ranRef = useRef(false);

  useEffect(() => {
    // Guards against React StrictMode's dev-only double-invoke — the token
    // in the fragment should only be adopted once.
    if (ranRef.current) return;
    ranRef.current = true;

    const queryError = searchParams.get("error");
    const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = hashParams.get("access_token");

    if (queryError) {
      setError(
        queryError === "missing_code"
          ? "Google did not return an authorization code."
          : queryError,
      );
      return;
    }
    if (!accessToken) {
      setError("Google sign-in did not return a session token.");
      return;
    }

    completeGoogleRedirect(accessToken)
      .then(() => navigate("/app/dashboard", { replace: true }))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError(
            err.status === 0
              ? "Could not reach the backend."
              : err.detail ?? "Google sign-in failed.",
          );
        } else {
          setError("Google sign-in failed.");
        }
      });
    // Intentionally run once on mount — see ranRef above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="absolute right-4 top-4 z-20">
        <ThemeToggle />
      </div>
      <div className="hero-enter w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <Brand size="lg" />
        </div>

        <div className="rounded-xl border border-line bg-surface-alt p-8 text-center shadow-[0_20px_45px_-30px_rgb(0_0_0_/_0.6)]">
          {error ? (
            <>
              <h1 className="mb-2 text-xl font-bold tracking-tight text-ink">Sign-in failed</h1>
              <p role="alert" className="mb-4 rounded-md bg-down-soft px-3.5 py-2.5 text-sm text-down">
                {error}
              </p>
              <Link to="/login" className="text-sm font-semibold text-ink underline underline-offset-2">
                Back to login
              </Link>
            </>
          ) : (
            <p role="status" className="flex items-center justify-center gap-2.5 text-sm text-ink-muted">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
              Signing you in with Google…
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
