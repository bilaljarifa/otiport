import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBillingStatus } from "../lib/billingApi";
import { billingStatusKey } from "../lib/queries";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";
import { buttonClass } from "../components/buttonStyles";

const POLL_MS = 2_000;
const TIMEOUT_MS = 20_000;

/**
 * Landed on after a successful Stripe Checkout redirect — but a redirect
 * only means the *browser* came back, not that the subscription is active
 * yet. That confirmation comes from Stripe's webhook, asynchronously, and
 * can arrive a second or two after this page loads. So this page never
 * says "you're upgraded" on its own: it polls `GET /billing/status` (the
 * user's own cached copy of what the webhook has applied so far) until the
 * plan reflects the upgrade, or gives up after ~20s and points at the
 * Billing page instead of guessing.
 */
export function BillingSuccessPage() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => setTimedOut(true), TIMEOUT_MS);
    return () => clearTimeout(id);
  }, []);

  const billing = useQuery({
    queryKey: billingStatusKey,
    queryFn: getBillingStatus,
    refetchInterval: (query) => {
      const plan = query.state.data?.plan;
      if (plan && plan !== "free") return false;
      return timedOut ? false : POLL_MS;
    },
  });

  const confirmed = billing.data && billing.data.plan !== "free";

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-surface px-4">
      <div className="absolute right-4 top-4 z-20">
        <ThemeToggle />
      </div>
      <div className="hero-enter w-full max-w-sm text-center">
        <div className="mb-8 flex justify-center">
          <Brand size="lg" />
        </div>

        <div className="rounded-xl border border-line bg-surface-alt p-8">
          {confirmed ? (
            <>
              <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-up-soft text-up">
                <svg viewBox="0 0 16 16" className="h-5 w-5" fill="none" aria-hidden="true">
                  <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <h1 className="text-xl font-bold tracking-tight text-ink">You're all set</h1>
              <p className="mt-2 text-sm text-ink-muted">
                Your {billing.data?.plan} subscription is active.
              </p>
              <Link to="/app/billing" className={buttonClass("accent", "mt-6 w-full py-2.5")}>
                Go to Billing
              </Link>
            </>
          ) : timedOut ? (
            <>
              <h1 className="text-xl font-bold tracking-tight text-ink">Payment received</h1>
              <p className="mt-2 text-sm text-ink-muted">
                Your payment went through, but activating your subscription is taking longer than usual. Check your
                Billing page in a moment — it updates automatically once confirmed.
              </p>
              <Link to="/app/billing" className={buttonClass("primary", "mt-6 w-full py-2.5")}>
                Go to Billing
              </Link>
            </>
          ) : (
            <>
              <svg className="mx-auto h-8 w-8 animate-spin text-ink-muted" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
              <h1 className="mt-4 text-xl font-bold tracking-tight text-ink">Confirming your payment…</h1>
              <p className="mt-2 text-sm text-ink-muted">
                Stripe is finalizing your subscription. This usually takes just a few seconds.
              </p>
            </>
          )}
        </div>
        {sessionId && <p className="mt-4 text-xs text-ink-faint">Checkout session {sessionId.slice(0, 24)}…</p>}
      </div>
    </div>
  );
}
