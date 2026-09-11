import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/apiClient";
import { Brand } from "../components/Brand";
import { Button } from "../components/Button";

export function LoginPage() {
  const { loginWithCredentials } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    // Trim accidental whitespace (copy-paste, autofill) — a stray space
    // must not silently turn a correct password into "wrong credentials".
    const trimmedUsername = username.trim();
    const trimmedPassword = password.trim();
    if (!trimmedUsername || !trimmedPassword) {
      setError("Username and password are required.");
      return;
    }

    setIsSubmitting(true);
    try {
      await loginWithCredentials(trimmedUsername, trimmedPassword);
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 0
            ? "Could not reach the backend. Is the API running on port 8000?"
            : err.detail ?? "Login failed.",
        );
      } else {
        setError("Login failed.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="theme-light-forced flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <Brand size="lg" />
          <p className="text-sm text-ink-muted">
            ETF portfolio intelligence — forecasting, market analysis and
            portfolio optimization.
          </p>
        </div>

        <div className="rounded-md border border-line bg-surface p-8">
          <h1 className="mb-6 text-lg font-bold text-ink">Welcome back</h1>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Username
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
              />
            </label>

            {error && (
              <p role="alert" className="rounded bg-down-soft px-3 py-2 text-sm text-down">
                {error}
              </p>
            )}

            <Button type="submit" disabled={isSubmitting} className="mt-2 w-full">
              {isSubmitting ? "Signing in…" : "Log in"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-muted">
            Don't have an account?{" "}
            <Link to="/register" className="font-semibold text-ink underline underline-offset-2">
              Create account
            </Link>
          </p>
        </div>

        <p className="mt-6 text-center text-sm">
          <Link to="/" className="text-ink-muted hover:text-ink">
            ← Back to home
          </Link>
        </p>
      </div>
    </div>
  );
}
