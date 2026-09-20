import { apiRequest } from "./apiClient";

export type Plan = "free" | "pro" | "premium";
export type PaidPlan = "pro" | "premium";
export type PaymentMode = "demo" | "stripe";

export interface BillingStatus {
  plan: Plan;
  subscription_status: string | null;
  current_period_end: string | null;
  stripe_configured: boolean;
  has_billing_account: boolean;
  payment_mode: PaymentMode;
}

export interface DemoCard {
  card_number: string;
  exp: string;
  cvc: string;
  cardholder_name: string;
}

export function getBillingStatus(): Promise<BillingStatus> {
  return apiRequest<BillingStatus>("/billing/status");
}

export function createCheckoutSession(plan: PaidPlan): Promise<{ url: string }> {
  return apiRequest<{ url: string }>("/billing/checkout", { method: "POST", body: { plan } });
}

export function createPortalSession(): Promise<{ url: string }> {
  return apiRequest<{ url: string }>("/billing/portal", { method: "POST" });
}

/** `PAYMENT_MODE=demo`'s equivalent of Stripe Checkout — one call, no
 * external redirect. The card fields only ever live in this request's
 * body; nothing on the frontend persists them beyond the form state that's
 * about to be submitted. */
export function createDemoCheckout(plan: PaidPlan, card: DemoCard): Promise<BillingStatus> {
  return apiRequest<BillingStatus>("/billing/demo-checkout", { method: "POST", body: { plan, ...card } });
}
