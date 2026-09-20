import { Link } from "react-router-dom";
import { Brand } from "../components/Brand";
import { ThemeToggle } from "../components/ThemeToggle";
import { buttonClass } from "../components/buttonStyles";

/** Landed on when a Stripe Checkout is closed/canceled before completion —
 * no charge was ever made, and no plan change happens on this app's side
 * either (Checkout was simply never completed). */
export function BillingCancelPage() {
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
          <h1 className="text-xl font-bold tracking-tight text-ink">Checkout canceled</h1>
          <p className="mt-2 text-sm text-ink-muted">No charge was made and your plan hasn't changed.</p>
          <div className="mt-6 flex flex-col gap-2.5">
            <Link to="/pricing" className={buttonClass("primary", "w-full py-2.5")}>
              Back to pricing
            </Link>
            <Link to="/app/billing" className={buttonClass("secondary", "w-full py-2.5")}>
              Go to Billing
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
