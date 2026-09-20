import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { useBillingStatus } from "../lib/queries";
import { createCheckoutSession, type PaidPlan, type Plan, type PaymentMode } from "../lib/billingApi";
import { ApiError } from "../lib/apiClient";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";
import { buttonClass } from "../components/buttonStyles";

interface PlanDef {
  id: Plan;
  name: string;
  price: string;
  tagline: string;
  features: string[];
  emphasized?: boolean;
}

const PLANS: PlanDef[] = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    tagline: "Get a feel for the platform.",
    features: ["Basic market data", "Limited forecasts", "Limited AI usage", "Basic analytics"],
  },
  {
    id: "pro",
    name: "Pro",
    price: "$9.99",
    tagline: "For active, research-driven investors.",
    emphasized: true,
    features: [
      "Full forecasting",
      "News Analytics",
      "Risk Center",
      "AI Assistant",
      "Advanced analytics",
      "More backtesting",
    ],
  },
  {
    id: "premium",
    name: "Premium",
    price: "$19.99",
    tagline: "The complete Optiport toolkit.",
    features: [
      "Everything in Pro",
      "Advanced optimization",
      "Advanced analytics",
      "Advanced backtesting",
      "Higher / unlimited AI usage",
    ],
  },
];

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4 shrink-0 text-accent" fill="none" aria-hidden="true">
      <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlanCard({
  plan,
  isAuthenticated,
  currentPlan,
  paymentMode,
  billingLoading,
  stripeConfigured,
  isPending,
  onUpgrade,
}: {
  plan: PlanDef;
  isAuthenticated: boolean;
  currentPlan: Plan | undefined;
  paymentMode: PaymentMode | undefined;
  billingLoading: boolean;
  stripeConfigured: boolean;
  isPending: boolean;
  onUpgrade: (plan: PaidPlan) => void;
}) {
  const isCurrent = isAuthenticated && currentPlan === plan.id;
  const isFree = plan.id === "free";
  // Demo mode never needs Stripe configured at all — only the real Stripe
  // path can be blocked on missing credentials.
  const blockedOnStripeConfig = paymentMode === "stripe" && !stripeConfigured;

  let ctaLabel: string;
  let disabled = false;
  if (isCurrent) {
    ctaLabel = "Current plan";
    disabled = true;
  } else if (isFree) {
    ctaLabel = isAuthenticated ? "Included" : "Get started";
    disabled = isAuthenticated;
  } else if (isAuthenticated && billingLoading) {
    // Which checkout to start (demo vs. Stripe) depends on knowing
    // `payment_mode` first — never guess by letting a click through before
    // that's loaded, since guessing wrong would start the wrong flow.
    ctaLabel = "Loading…";
    disabled = true;
  } else {
    ctaLabel = isPending ? "Redirecting…" : `Upgrade to ${plan.name}`;
    disabled = isPending || (isAuthenticated && blockedOnStripeConfig);
  }

  function handleClick() {
    if (disabled || isCurrent) return;
    if (isFree) return; // "Get started" is a Link, not this handler
    onUpgrade(plan.id as PaidPlan);
  }

  return (
    <div
      className={`relative flex flex-col rounded-md border p-6 ${
        plan.emphasized ? "border-accent" : "border-line"
      }`}
    >
      {plan.emphasized && (
        <span className="absolute -top-3 left-6 rounded-full border border-accent bg-surface px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-accent">
          Most popular
        </span>
      )}
      <div className="text-sm font-bold uppercase tracking-wide text-ink">{plan.name}</div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="font-mono text-3xl font-extrabold text-ink">{plan.price}</span>
        <span className="text-sm text-ink-faint">/month</span>
      </div>
      <p className="mt-2 text-sm text-ink-muted">{plan.tagline}</p>

      <ul className="mt-6 flex flex-col gap-2.5">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm text-ink-muted">
            <CheckIcon />
            {f}
          </li>
        ))}
      </ul>

      <div className="mt-6">
        {isFree && !isAuthenticated ? (
          <Link to="/register" className={buttonClass("primary", "w-full py-2.5")}>
            {ctaLabel}
          </Link>
        ) : (
          <button
            type="button"
            onClick={handleClick}
            disabled={disabled}
            className={buttonClass(plan.emphasized ? "accent" : "primary", "w-full py-2.5")}
          >
            {ctaLabel}
          </button>
        )}
        {!isFree && isAuthenticated && blockedOnStripeConfig && !isCurrent && (
          <p className="mt-2 text-center text-xs text-ink-faint">Billing isn't configured on this deployment yet.</p>
        )}
      </div>
    </div>
  );
}

/**
 * Public pricing page — reachable signed out (marketing) or signed in (the
 * Billing page's "Upgrade" button lands here). Which checkout a paid-plan
 * click starts depends on the server's own `payment_mode` (from
 * `GET /billing/status`, only known once authenticated): "stripe" redirects
 * to a real Stripe Checkout Session; "demo" — used whenever real Stripe
 * credentials aren't available, e.g. this project's PFE presentation —
 * goes to the in-app simulated checkout instead. Neither path marks a user
 * as upgraded from this page itself: Stripe's webhook confirms a real
 * subscription (see `BillingSuccess.tsx`), and the demo checkout confirms
 * its own simulated one synchronously on its own page.
 */
export function PricingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const billing = useBillingStatus({ enabled: isAuthenticated });
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  const checkoutMutation = useMutation({
    mutationFn: createCheckoutSession,
    onSuccess: (data) => {
      window.location.href = data.url;
    },
    onError: (err) => {
      setCheckoutError(err instanceof ApiError ? (err.detail ?? err.message) : "Could not start checkout.");
    },
  });

  function handleUpgrade(plan: PaidPlan) {
    setCheckoutError(null);
    if (!isAuthenticated) {
      navigate("/register");
      return;
    }
    // `PlanCard` already disables the button until `billing.data` is
    // loaded, but never fall back to a real Stripe charge attempt on a
    // stale/missing read of the mode — demo is always the safe default.
    if (billing.data?.payment_mode !== "stripe") {
      navigate(`/checkout/demo?plan=${plan}`);
      return;
    }
    checkoutMutation.mutate(plan);
  }

  return (
    <div className="min-h-screen bg-surface">
      <nav className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3.5 sm:px-6">
          <Link to="/" className="min-w-0 shrink">
            <Brand size="sm" />
          </Link>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
            <ThemeToggle />
            {isAuthenticated ? (
              <Link to="/app/dashboard" className="text-sm font-semibold text-ink-muted hover:text-ink">
                Dashboard
              </Link>
            ) : (
              <>
                <Link to="/login" className="hidden text-sm font-semibold text-ink-muted hover:text-ink sm:inline">
                  Sign in
                </Link>
                <Link to="/register" className={buttonClass("primary", "px-2.5 py-1.5 text-xs sm:px-3.5 sm:text-sm")}>
                  Create account
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">Simple, transparent pricing</h1>
          <p className="mt-3 text-sm text-ink-muted sm:text-base">
            Start free. Upgrade when you need deeper forecasting, news intelligence and analytics.
          </p>
        </div>

        {checkoutError && (
          <p role="alert" className="mx-auto mt-6 max-w-md rounded-md bg-down-soft px-3.5 py-2.5 text-center text-sm text-down">
            {checkoutError}
          </p>
        )}

        <div className="mx-auto mt-12 grid max-w-5xl gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {PLANS.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              isAuthenticated={isAuthenticated}
              currentPlan={billing.data?.plan}
              paymentMode={billing.data?.payment_mode}
              billingLoading={isAuthenticated && billing.isLoading}
              stripeConfigured={billing.data?.stripe_configured ?? false}
              isPending={checkoutMutation.isPending && checkoutMutation.variables === plan.id}
              onUpgrade={handleUpgrade}
            />
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-xl text-center text-xs text-ink-faint">
          Optiport is a simulated paper-trading platform — no real funds or brokerage involved.{" "}
          {billing.data?.payment_mode === "stripe"
            ? "Payments are processed securely by Stripe; card details are never stored on Optiport's servers."
            : "Upgrades in this environment use a simulated demo payment — no real charge is ever made and no card details are stored."}
        </p>
      </div>
    </div>
  );
}
