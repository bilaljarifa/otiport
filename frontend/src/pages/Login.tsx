import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/apiClient";
import { Button } from "../components/Button";
import { AuthLayout } from "../components/auth/AuthLayout";
import { PasswordInput } from "../components/auth/PasswordInput";
import { GoogleContinueButton } from "../components/auth/GoogleContinueButton";

const INPUT_CLASS =
  "w-full rounded-md border border-line-strong bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent/30";

export function LoginPage() {
  const { loginWithCredentials } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showForgotNote, setShowForgotNote] = useState(false);

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
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your Optiport workspace."
      footer={
        <p className="text-center text-sm text-ink-muted">
          Don't have an account?{" "}
          <Link to="/register" className="font-semibold text-ink underline underline-offset-2">
            Create account
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <label htmlFor="login-username" className="flex flex-col gap-1.5 text-sm font-medium text-ink">
          Username
          <input
            id="login-username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            className={INPUT_CLASS}
          />
        </label>

        <PasswordInput
          label="Password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />

        <div className="-mt-2 flex justify-end">
          <button
            type="button"
            onClick={() => setShowForgotNote((v) => !v)}
            className="text-xs font-medium text-ink-muted underline underline-offset-2 hover:text-ink"
          >
            Forgot password?
          </button>
        </div>
        {showForgotNote && (
          <p className="-mt-2 text-xs text-ink-faint">
            Password resets aren't available in this demo build — contact your administrator.
          </p>
        )}

        {error && (
          <p role="alert" className="rounded-md bg-down-soft px-3.5 py-2.5 text-sm text-down">
            {error}
          </p>
        )}

        <Button
          type="submit"
          variant="accent"
          disabled={isSubmitting}
          className="mt-2 w-full py-2.5"
        >
          {isSubmitting ? (
            <span className="inline-flex items-center gap-2">
              <Spinner /> Signing in…
            </span>
          ) : (
            "Sign In →"
          )}
        </Button>
      </form>

      <GoogleContinueButton />
    </AuthLayout>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
