import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/apiClient";
import { Brand } from "../components/Brand";
import { Button } from "../components/Button";

export function RegisterPage() {
  const { registerAccount } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    const values = {
      fullName: fullName.trim(),
      username: username.trim(),
      email: email.trim(),
      password: password.trim(),
      confirm: confirm.trim(),
    };

    if (!values.fullName || !values.username || !values.email || !values.password || !values.confirm) {
      setError("All fields are required.");
      return;
    }
    if (!/^[a-zA-Z0-9_.-]{3,32}$/.test(values.username)) {
      setError("Username must be 3–32 characters: letters, digits, dots, dashes or underscores.");
      return;
    }
    if (values.password !== values.confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (values.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setIsSubmitting(true);
    try {
      await registerAccount(values.username, values.email, values.password, values.fullName);
      // Backend already created the $250,000 simulated account as part of
      // registration (see backend/crud.py::create_user) — the token we just
      // received is already valid, so this is a real authenticated session,
      // not a redirect-and-hope.
      navigate("/app/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 0
            ? "Could not reach the backend. Is the API running on port 8000?"
            : err.detail ?? "Registration failed.",
        );
      } else {
        setError("Registration failed.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="theme-light-forced flex min-h-screen items-center justify-center bg-surface px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <Brand size="lg" />
          <p className="text-sm text-ink-muted">
            Every account starts with $250,000 in simulated capital.
          </p>
        </div>

        <div className="rounded-md border border-line bg-surface p-8">
          <h1 className="mb-6 text-lg font-bold text-ink">Create your Optiport account</h1>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Full name
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Username
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
              />
              <span className="text-xs text-ink-faint">
                3–32 characters: letters, digits, dots, dashes or underscores.
              </span>
            </label>

            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
              />
              <span className="text-xs text-ink-faint">8 characters minimum.</span>
            </label>

            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Confirm password
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
              />
            </label>

            {error && (
              <p role="alert" className="rounded bg-down-soft px-3 py-2 text-sm text-down">
                {error}
              </p>
            )}

            <Button type="submit" disabled={isSubmitting} className="mt-2 w-full">
              {isSubmitting ? "Creating account…" : "Create account"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-muted">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-ink underline underline-offset-2">
              Log in
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
