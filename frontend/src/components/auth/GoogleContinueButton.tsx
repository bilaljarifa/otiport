import { useEffect, useState } from "react";
import { googleConfig } from "../../lib/authApi";
import { buttonClass } from "../buttonStyles";

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.68-3.87 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.8.54-1.83.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.16.28-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58Z"
      />
    </svg>
  );
}

/**
 * "Continue with Google" — same authorization-code redirect on both Login
 * and Register (Google sign-in already creates an account on first use,
 * see `backend/crud.py::get_or_create_google_user`, so there is only ever
 * one real flow to trigger, not a separate "register with Google"). Renders
 * nothing until the backend confirms Google is actually configured — never
 * shows a button that can't work.
 */
export function GoogleContinueButton() {
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [googleClientId, setGoogleClientId] = useState<string | null>(null);
  const [googleRedirectUri, setGoogleRedirectUri] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    googleConfig()
      .then((cfg) => {
        if (cancelled) return;
        setGoogleEnabled(cfg.enabled);
        setGoogleClientId(cfg.client_id);
        setGoogleRedirectUri(cfg.redirect_uri);
      })
      .catch(() => {
        // Backend unreachable or the check itself failed — fail closed.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!googleEnabled) return null;

  function handleClick() {
    if (!googleClientId || !googleRedirectUri) return;
    const params = new URLSearchParams({
      client_id: googleClientId,
      redirect_uri: googleRedirectUri,
      response_type: "code",
      scope: "openid email profile",
      access_type: "online",
      prompt: "select_account",
    });
    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
  }

  return (
    <>
      <div className="my-5 flex items-center gap-3 text-xs font-medium uppercase tracking-wide text-ink-faint">
        <div className="h-px flex-1 bg-line" />
        or
        <div className="h-px flex-1 bg-line" />
      </div>
      <button type="button" onClick={handleClick} className={buttonClass("secondary", "w-full py-2.5")}>
        <GoogleIcon />
        Continue with Google
      </button>
    </>
  );
}
