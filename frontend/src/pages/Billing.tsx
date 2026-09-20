import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useBillingStatus } from "../lib/queries";
import { createPortalSession } from "../lib/billingApi";
import type { Plan } from "../lib/billingApi";
import { ApiError } from "../lib/apiClient";
import { QueryState } from "../components/QueryState";
import { StatTile } from "../components/StatTile";
import { Badge } from "../components/Badge";
import { buttonClass } from "../components/buttonStyles";

const PLAN_LABELS: Record<Plan, string> = { free: "Free", pro: "Pro", premium: "Premium" };
const PLAN_PRICES: Record<Plan, string> = { free: "$0/month", pro: "$9.99/month", premium: "$19.99/month" };

function statusTone(status: string | null): string {
  if (status === "active" || status === "trialing") return "bg-up-soft text-up";
  if (status === "past_due" || status === "unpaid") return "bg-down-soft text-down";
  if (status === "canceled" || status === "incomplete_expired") return "bg-surface-alt text-ink-muted";
  return "bg-surface-alt text-ink-muted";
}

function formatRenewalDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

/**
 * Authenticated billing overview. Everything shown here is `User`'s own
 * cached copy of Stripe's state (`GET /billing/status`) — the webhook in
 * `backend/routers/billing.py` is what actually keeps it in sync, not
 * anything this page does. "Manage Billing" hands the browser to the real
 * Stripe Customer Portal for payment method changes, invoices and
 * cancellation — there is no separate cancel flow to duplicate that.
 */
export function BillingPage() {
  const billing = useBillingStatus();
  const [portalError, setPortalError] = useState<string | null>(null);

  const portalMutation = useMutation({
    mutationFn: createPortalSession,
    onSuccess: (data) => {
      window.location.href = data.url;
    },
    onError: (err) => {
      setPortalError(err instanceof ApiError ? (err.detail ?? err.message) : "Could not open the billing portal.");
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-ink">Billing</h1>
        <p className="mt-1 text-xs text-ink-faint">
          {billing.data?.payment_mode === "demo"
            ? "Your Optiport plan and subscription. This environment uses simulated demo payments."
            : "Your Optiport plan and subscription, managed securely through Stripe."}
        </p>
      </div>

      <QueryState isLoading={billing.isLoading} isError={billing.isError} error={billing.error} onRetry={() => billing.refetch()}>
        {billing.data && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Current plan" value={PLAN_LABELS[billing.data.plan]} />
              <StatTile label="Price" value={PLAN_PRICES[billing.data.plan]} />
              <div className="rounded-md border border-line p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Status</div>
                <div className="mt-1.5">
                  {billing.data.subscription_status ? (
                    <Badge tone={statusTone(billing.data.subscription_status)}>{billing.data.subscription_status}</Badge>
                  ) : (
                    <span className="font-mono text-xl font-bold text-ink">—</span>
                  )}
                </div>
              </div>
              <StatTile label="Renewal date" value={formatRenewalDate(billing.data.current_period_end)} />
            </div>

            {billing.data.payment_mode === "demo" ? (
              <div className="rounded-md border border-accent bg-accent-soft px-4 py-3 text-xs font-semibold uppercase tracking-wide text-accent">
                Demo payment mode — subscriptions are simulated for demonstration purposes.
              </div>
            ) : (
              !billing.data.stripe_configured && (
                <div className="rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
                  Billing is not configured on this deployment yet — upgrades and the billing portal are unavailable
                  until Stripe is set up.
                </div>
              )
            )}

            {portalError && (
              <p role="alert" className="rounded-md bg-down-soft px-3.5 py-2.5 text-sm text-down">
                {portalError}
              </p>
            )}

            <div className="flex flex-wrap gap-3">
              <Link to="/pricing" className={buttonClass("primary", "px-4 py-2")}>
                {billing.data.plan === "premium" ? "View plans" : "Upgrade"}
              </Link>
              <button
                type="button"
                onClick={() => {
                  setPortalError(null);
                  portalMutation.mutate();
                }}
                disabled={
                  portalMutation.isPending || !billing.data.stripe_configured || !billing.data.has_billing_account
                }
                className={buttonClass("secondary", "px-4 py-2")}
              >
                {portalMutation.isPending ? "Opening…" : "Manage billing"}
              </button>
            </div>
            {billing.data.payment_mode === "demo" ? (
              <p className="text-xs text-ink-faint">
                "Manage billing" isn't available in demo payment mode — there is no real Stripe subscription behind
                a simulated plan.
              </p>
            ) : (
              billing.data.plan === "free" &&
              !billing.data.has_billing_account && (
                <p className="text-xs text-ink-faint">
                  "Manage billing" becomes available once you've subscribed to a paid plan.
                </p>
              )
            )}
          </div>
        )}
      </QueryState>
    </div>
  );
}
