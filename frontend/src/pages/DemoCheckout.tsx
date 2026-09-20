import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createDemoCheckout, type PaidPlan } from "../lib/billingApi";
import { billingStatusKey } from "../lib/queries";
import { ApiError } from "../lib/apiClient";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";
import { buttonClass } from "../components/buttonStyles";

const PLAN_INFO: Record<PaidPlan, { name: string; price: string }> = {
  pro: { name: "Pro", price: "$9.99" },
  premium: { name: "Premium", price: "$19.99" },
};

const DEMO_CARD_NUMBER = "4242 4242 4242 4242";

const INPUT_CLASS =
  "w-full rounded-md border border-line-strong bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent/30";

function CheckCircleIcon() {
  return (
    <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-up-soft text-up">
      <svg viewBox="0 0 16 16" className="h-5 w-5" fill="none" aria-hidden="true">
        <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

/**
 * `PAYMENT_MODE=demo`'s checkout — used whenever real Stripe credentials
 * aren't available (this project's PFE presentation, or any dev setup
 * without a Stripe account). Nothing here talks to a payment provider: a
 * passing `POST /billing/demo-checkout` call *is* the simulated charge,
 * confirmed synchronously (no webhook to wait on, unlike the real Stripe
 * path in `BillingSuccess.tsx`). The entered card fields exist only in
 * this component's own state for the duration of one submit — they are
 * never written anywhere else, and this page never claims to be Stripe or
 * any real payment network.
 */
export function DemoCheckoutPage() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const requestedPlan = searchParams.get("plan");
  const plan: PaidPlan = requestedPlan === "premium" ? "premium" : "pro";
  const planInfo = PLAN_INFO[plan];

  const [cardNumber, setCardNumber] = useState("");
  const [exp, setExp] = useState("");
  const [cvc, setCvc] = useState("");
  const [cardholderName, setCardholderName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      createDemoCheckout(plan, { card_number: cardNumber, exp, cvc, cardholder_name: cardholderName }),
    onSuccess: (status) => {
      queryClient.setQueryData(billingStatusKey, status);
      setSuccess(true);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? (err.detail ?? err.message) : "Payment failed.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mutation.isPending) return;
    setError(null);

    if (!cardholderName.trim()) {
      setError("Enter the cardholder name.");
      return;
    }
    const digits = cardNumber.replace(/\D/g, "");
    if (digits.length < 13 || digits.length > 19) {
      setError("Enter a valid card number.");
      return;
    }
    if (!/^\d{2}\/\d{2}$/.test(exp.trim())) {
      setError("Enter the expiry date as MM/YY.");
      return;
    }
    if (!/^\d{3,4}$/.test(cvc.trim())) {
      setError("Enter a valid 3 or 4 digit CVC.");
      return;
    }

    mutation.mutate();
  }

  function fillDemoCard() {
    setCardNumber(DEMO_CARD_NUMBER);
    setExp("12/30");
    setCvc("123");
  }

  if (success) {
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
            <CheckCircleIcon />
            <h1 className="text-xl font-bold tracking-tight text-ink">Payment successful</h1>
            <p className="mt-2 text-sm text-ink-muted">Your {planInfo.name} plan is now active.</p>
            <Link to="/app/billing" className={buttonClass("accent", "mt-6 w-full py-2.5")}>
              Go to Billing
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center bg-surface px-4 py-10">
      <div className="absolute right-4 top-4 z-20">
        <ThemeToggle />
      </div>
      <Link to="/" className="mb-6">
        <Brand size="md" />
      </Link>

      <div className="w-full max-w-md">
        <div className="rounded-md border border-accent bg-accent-soft px-4 py-3 text-center text-xs font-bold uppercase tracking-wide text-accent">
          Demo payment — no real money will be charged
        </div>

        <div className="mt-6 rounded-xl border border-line bg-surface-alt p-6 sm:p-8">
          <div className="text-center">
            <div className="text-xs font-bold uppercase tracking-wide text-ink-faint">{planInfo.name} plan</div>
            <div className="mt-1 text-2xl font-extrabold text-ink">
              {planInfo.price} <span className="text-sm font-normal text-ink-faint">/ month</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4" noValidate>
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Payment method</div>

            <div>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <label htmlFor="demo-card-number" className="text-sm font-medium text-ink">
                  Card number
                </label>
                <button type="button" onClick={fillDemoCard} className="shrink-0 text-xs font-semibold text-accent hover:underline">
                  Use demo card
                </button>
              </div>
              <input
                id="demo-card-number"
                inputMode="numeric"
                autoComplete="off"
                placeholder="4242 4242 4242 4242"
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                className={INPUT_CLASS}
              />
              <p className="mt-1.5 text-xs text-ink-faint">Demo card: 4242 4242 4242 4242 — no other number is valid here.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <label htmlFor="demo-exp" className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                MM/YY
                <input
                  id="demo-exp"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="12/30"
                  value={exp}
                  onChange={(e) => setExp(e.target.value)}
                  className={INPUT_CLASS}
                />
              </label>
              <label htmlFor="demo-cvc" className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                CVC
                <input
                  id="demo-cvc"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="123"
                  value={cvc}
                  onChange={(e) => setCvc(e.target.value)}
                  className={INPUT_CLASS}
                />
              </label>
            </div>

            <label htmlFor="demo-cardholder" className="flex flex-col gap-1.5 text-sm font-medium text-ink">
              Cardholder name
              <input
                id="demo-cardholder"
                autoComplete="off"
                value={cardholderName}
                onChange={(e) => setCardholderName(e.target.value)}
                className={INPUT_CLASS}
              />
            </label>

            <div className="mt-1 rounded-md border border-line-soft bg-surface px-4 py-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">Order summary</div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-ink-muted">{planInfo.name}</span>
                <span className="font-mono font-semibold text-ink">{planInfo.price} / month</span>
              </div>
            </div>

            {error && (
              <p role="alert" className="rounded-md bg-down-soft px-3.5 py-2.5 text-sm text-down">
                {error}
              </p>
            )}

            <button type="submit" disabled={mutation.isPending} className={buttonClass("accent", "w-full py-2.5")}>
              {mutation.isPending ? "Processing…" : `Pay ${planInfo.price}`}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-ink-faint">
          <Link to="/pricing" className="underline underline-offset-2 hover:text-ink">
            Back to pricing
          </Link>
        </p>
      </div>
    </div>
  );
}
