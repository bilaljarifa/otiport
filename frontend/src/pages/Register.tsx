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

const USERNAME_PATTERN = /^[a-zA-Z0-9_.-]{3,32}$/;

function RequirementRow({
  met,
  children,
  className = "",
}: {
  met: boolean;
  children: string;
  className?: string;
}) {
  return (
    <li className={`flex items-center gap-2 text-xs ${met ? "text-up" : "text-ink-faint"} ${className}`}>
      <span
        className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border ${
          met ? "border-up bg-up-soft" : "border-line-strong"
        }`}
        aria-hidden="true"
      >
        {met && (
          <svg viewBox="0 0 12 12" className="h-2 w-2" fill="none">
            <path d="M2 6l2.5 2.5L10 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      {children}
    </li>
  );
}

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

  const hasMinLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecialChar = /[^A-Za-z0-9]/.test(password);
  const passwordsMatch = confirm.length > 0 && password === confirm;
  const usernameValid = username.length === 0 || USERNAME_PATTERN.test(username);
  const passwordMeetsRequirements = hasMinLength && hasUppercase && hasNumber && hasSpecialChar;

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
    if (!USERNAME_PATTERN.test(values.username)) {
      setError("Username must be 3–32 characters: letters, digits, dots, dashes or underscores.");
      return;
    }
    if (values.password !== values.confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (!passwordMeetsRequirements) {
      setError("Password must be at least 8 characters and include an uppercase letter, a number and a special character.");
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
    <AuthLayout
      title="Create your account"
      subtitle="Start building and analyzing your simulated portfolio."
      footer={
        <p className="text-center text-sm text-ink-muted">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-ink underline underline-offset-2">
            Sign in
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <label htmlFor="reg-fullname" className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Full name
            <input
              id="reg-fullname"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              className={INPUT_CLASS}
            />
          </label>

          <label htmlFor="reg-username" className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Username
            <input
              id="reg-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              aria-invalid={!usernameValid}
              className={INPUT_CLASS}
            />
          </label>
        </div>
        <p className="-mt-2.5 text-xs text-ink-faint">Username: 3–32 characters — letters, digits, dots, dashes or underscores.</p>

        <label htmlFor="reg-email" className="flex flex-col gap-1.5 text-sm font-medium text-ink">
          Email
          <input
            id="reg-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            className={INPUT_CLASS}
          />
        </label>

        <PasswordInput label="Password" value={password} onChange={setPassword} autoComplete="new-password" />
        <PasswordInput label="Confirm password" value={confirm} onChange={setConfirm} autoComplete="new-password" />

        <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 rounded-md border border-line-soft bg-surface-alt px-3.5 py-3">
          <RequirementRow met={hasMinLength}>At least 8 characters</RequirementRow>
          <RequirementRow met={hasUppercase}>Uppercase letter</RequirementRow>
          <RequirementRow met={hasNumber}>Number</RequirementRow>
          <RequirementRow met={hasSpecialChar}>Special character</RequirementRow>
          <RequirementRow met={passwordsMatch} className="col-span-2 border-t border-line-soft pt-1.5">
            Passwords match
          </RequirementRow>
        </ul>

        {error && (
          <p role="alert" className="rounded-md bg-down-soft px-3.5 py-2.5 text-sm text-down">
            {error}
          </p>
        )}

        <Button
          type="submit"
          variant="accent"
          disabled={
            isSubmitting ||
            (password.length > 0 && !passwordMeetsRequirements) ||
            (confirm.length > 0 && !passwordsMatch)
          }
          className="mt-2 w-full py-2.5"
        >
          {isSubmitting ? (
            <span className="inline-flex items-center gap-2">
              <Spinner /> Creating account…
            </span>
          ) : (
            "Create Account →"
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
