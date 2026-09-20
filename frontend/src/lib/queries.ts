import { useMutation, useQuery } from "@tanstack/react-query";
import { getAlerts, getAttribution, getEquityCurve, getPortfolioSummary, getWatchlist } from "./portfolioApi";
import { getBillingStatus } from "./billingApi";
import { getMarketImpact } from "./newsApi";
import { getOhlc, getPublicQuotes, getQuotes, type ChartPeriod } from "./marketApi";
import { getStats, listUsers } from "./adminApi";
import { getTickerNews, getTickerNewsSummary } from "./newsApi";
import { getNewsAnalytics } from "./newsAnalyticsApi";
import { getAssistantStatus } from "./assistantApi";
import {
  getModelEvaluationDetail,
  getModelEvaluationSummary,
  getModelEvaluationUniverse,
  smartInvest,
  getMarketRegime,
  getModelComparison,
} from "./analyticsApi";
import { getPortfolioRisk } from "./riskApi";
import { getForecastContext } from "./forecastApi";
import { analyzeScenario } from "./scenarioApi";
import type { ScenarioHoldingInput } from "./scenarioApi";

/**
 * Centralized query keys/hooks — every page that needs the portfolio
 * summary or a set of quotes shares the same TanStack Query cache entry
 * instead of independently re-fetching, and gets the same short
 * revalidation window. Mirrors the intent of the Streamlit app's
 * `services/context.py` (fetch once per run, every page reads the same
 * snapshot) using TanStack Query's actual purpose-built mechanism for it.
 */

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ["portfolio", "summary"],
    queryFn: getPortfolioSummary,
    staleTime: 5_000, // matches the backend's own settle/sync throttle window
  });
}

export const watchlistKey = ["portfolio", "watchlist"] as const;

export function useWatchlist() {
  return useQuery({
    queryKey: watchlistKey,
    queryFn: getWatchlist,
    staleTime: 5_000,
  });
}

export const billingStatusKey = ["billing", "status"] as const;

/** Current plan/subscription state. Short staleTime so the Billing page
 * reflects a just-completed Checkout/webhook promptly; `refetchInterval`
 * lets the success page poll while it's waiting on the webhook to land
 * (see `BillingSuccess.tsx`) without every other caller paying for that.
 * `enabled` defaults to true for authenticated-only call sites (Billing);
 * the Pricing page, reachable signed out, passes `isAuthenticated` so a
 * logged-out visitor never fires a request that can only ever 401. */
export function useBillingStatus(options?: { refetchInterval?: number | false; enabled?: boolean }) {
  return useQuery({
    queryKey: billingStatusKey,
    queryFn: getBillingStatus,
    staleTime: 5_000,
    refetchInterval: options?.refetchInterval ?? false,
    enabled: options?.enabled ?? true,
  });
}

export const alertsKey = ["portfolio", "alerts"] as const;

/** Short staleTime: `AppShell`'s 60s settle poll can flip ACTIVE -> TRIGGERED
 * server-side at any time, and this page should reflect that promptly. */
export function useAlerts() {
  return useQuery({
    queryKey: alertsKey,
    queryFn: getAlerts,
    staleTime: 15_000,
  });
}

/** News impact for a whole ticker universe (the Markets screener) — the
 * exact `/news/market-impact` pipeline the News pages already use, just
 * batched instead of fetched once per ticker. */
export function useMarketImpact(tickers: string[]) {
  const key = [...tickers].sort().join(",");
  return useQuery({
    queryKey: ["news", "market-impact", key],
    queryFn: () => getMarketImpact(tickers),
    enabled: tickers.length > 0,
    staleTime: 15 * 60_000,
    retry: false,
  });
}

/** Trend/volatility regime classification — cheap to recompute but the
 * underlying price fetch is shared with everything else via
 * `market_cache`, so a modest staleTime avoids redundant calls on tab
 * switches. */
export function useMarketRegime(ticker: string) {
  return useQuery({
    queryKey: ["analytics", "market-regime", ticker],
    queryFn: () => getMarketRegime(ticker),
    staleTime: 10 * 60_000,
    retry: false,
  });
}

/** LSTM vs. non-ML baselines over the same chronological test split as
 * Model Evaluation — heavier (re-runs the LSTM's own eval plus 3 cheap
 * baselines), so a longer staleTime matching that module's own cache TTL. */
export function useModelComparison(ticker: string) {
  return useQuery({
    queryKey: ["analytics", "model-comparison", ticker],
    queryFn: () => getModelComparison(ticker),
    enabled: ticker.length > 0,
    staleTime: 15 * 60_000,
    retry: false,
  });
}

/** Per-ticker LSTM forecast + historical return/volatility for the Markets
 * screener — reuses `/smart-invest`'s existing batched allocation response
 * (the same numbers already shown in Analytics > Portfolio Optimizer) rather
 * than a second forecast pipeline. The chosen strategy/weights are ignored;
 * only the per-ticker `allocations` fields are read. */
export function useScreenerForecast(tickers: string[]) {
  const key = [...tickers].sort().join(",");
  return useQuery({
    queryKey: ["screener", "forecast", key],
    queryFn: () => smartInvest({ tickers, strategy: "equal_weight", risk_free_rate: 0.05 }),
    enabled: tickers.length > 0,
    staleTime: 15 * 60_000,
    retry: false,
  });
}

/** The full account history in one call — the Dashboard performance chart
 * slices this into 1D/1W/.../ALL ranges locally instead of re-fetching per
 * range. Reconstructed server-side from real transactions, not cheap
 * (a historical price fetch), so a longer staleTime than live quotes. */
export function useEquityCurve() {
  return useQuery({
    queryKey: ["portfolio", "equity-curve"],
    queryFn: getEquityCurve,
    staleTime: 60_000,
    retry: false,
  });
}

/** Which real holdings contributed to the account's total return — same
 * transaction ledger as the equity curve, similar cost, similar
 * staleTime. */
export function useAttribution() {
  return useQuery({
    queryKey: ["portfolio", "attribution"],
    queryFn: getAttribution,
    staleTime: 60_000,
    retry: false,
  });
}

export function useQuotes(tickers: string[]) {
  const key = [...tickers].sort().join(",");
  return useQuery({
    queryKey: ["market", "quotes", key],
    queryFn: () => getQuotes(tickers),
    enabled: tickers.length > 0,
    staleTime: 15_000, // backend quote_cache TTL is 20s — stay just under it
  });
}

/** Powers the public Landing page's market ticker — same `quote_cache`
 * backend, so the same 15s staleTime; a 30s refetch keeps it feeling
 * "live" for a visitor who leaves the tab open, without polling faster
 * than the underlying cache can ever actually change. */
export function usePublicMarketTicker() {
  return useQuery({
    queryKey: ["market", "public-ticker"],
    queryFn: getPublicQuotes,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useOhlc(ticker: string, period: ChartPeriod) {
  return useQuery({
    queryKey: ["market", "ohlc", ticker, period],
    queryFn: () => getOhlc(ticker, period),
    enabled: ticker.length > 0,
    staleTime: 55_000, // backend ohlc_cache TTL is 60s — stay just under it
  });
}

export const adminUsersKey = ["admin", "users"] as const;

export function useAdminUsers() {
  return useQuery({
    queryKey: adminUsersKey,
    queryFn: listUsers,
    staleTime: 5_000,
  });
}

export function useAdminStats() {
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: getStats,
    staleTime: 5_000,
  });
}

export function useTickerNews(ticker: string) {
  return useQuery({
    queryKey: ["news", "list", ticker],
    queryFn: () => getTickerNews(ticker),
    enabled: ticker.length > 0,
    staleTime: 15 * 60_000, // backend's analyzed-news cache is ~20 min — stay under it
    retry: false, // a missing/invalid NEWS_API_KEY returns 503 every time; retrying wastes calls
  });
}

export function useTickerNewsSummary(ticker: string) {
  return useQuery({
    queryKey: ["news", "summary", ticker],
    queryFn: () => getTickerNewsSummary(ticker),
    enabled: ticker.length > 0,
    staleTime: 15 * 60_000,
    retry: false,
  });
}

/** The wide-window (30-day) analytics pass — its own backend cache entry
 * (~20 min, separate from the feed's), so the same staleTime convention. */
export function useNewsAnalytics(ticker: string) {
  return useQuery({
    queryKey: ["news", "analytics", ticker],
    queryFn: () => getNewsAnalytics(ticker),
    enabled: ticker.length > 0,
    staleTime: 15 * 60_000,
    retry: false,
  });
}

/** The 12 ETFs with a trained model — backs the Model Evaluation ticker
 * picker. Static for the life of the deployment (models are trained
 * offline, not on request), so a long staleTime is safe. */
export function useModelEvaluationUniverse() {
  return useQuery({
    queryKey: ["analytics", "model-evaluation", "universe"],
    queryFn: getModelEvaluationUniverse,
    staleTime: 60 * 60_000,
    retry: false,
  });
}

/** Headline out-of-sample metrics for all 12 trained models. Backed by the
 * backend's own 30-minute evaluation cache (loading 12 Keras models + the
 * full feature history isn't free) — matching that here avoids refetching
 * on every tab switch back to Model Evaluation within that window. */
export function useModelEvaluationSummary() {
  return useQuery({
    queryKey: ["analytics", "model-evaluation", "summary"],
    queryFn: getModelEvaluationSummary,
    staleTime: 30 * 60_000,
    retry: false,
  });
}

export function useModelEvaluationDetail(ticker: string) {
  return useQuery({
    queryKey: ["analytics", "model-evaluation", "detail", ticker],
    queryFn: () => getModelEvaluationDetail(ticker),
    enabled: ticker.length > 0,
    staleTime: 30 * 60_000,
    retry: false,
  });
}

/** Recomputes from live prices + a fresh 1y history fetch, so it's not
 * free — matches `useQuotes`'s 15s staleTime (same backend price cache) but
 * doesn't auto-refetch on an interval; the Risk Center page refetches on
 * demand instead. */
export function usePortfolioRisk(benchmark = "SPY") {
  return useQuery({
    queryKey: ["risk", "portfolio", benchmark],
    queryFn: () => getPortfolioRisk(benchmark),
    staleTime: 15_000,
    retry: false,
  });
}

/** Loads an LSTM model + the news pipeline — not cheap, and both of those
 * already have their own backend caches (forecast: no cache but a single
 * model load; news: ~20min). A 15-minute staleTime avoids re-running this
 * on every tab switch while a user browses one ticker's Research page. */
export function useForecastContext(ticker: string, currentPrice?: number) {
  return useQuery({
    queryKey: ["forecast", "context", ticker, currentPrice ?? null],
    queryFn: () => getForecastContext(ticker, currentPrice),
    enabled: ticker.length > 0,
    staleTime: 15 * 60_000,
    retry: false,
  });
}

/** Scenario Analysis's "current" baseline — evaluated through the same
 * `/analytics/scenario` endpoint as the hypothetical scenario itself, so
 * both sides of the comparison share one methodology. Keyed on the actual
 * holdings/cash signature (not the raw object) plus benchmark/risk-free
 * inputs, so it only refetches when something that would change the result
 * actually changes — not on every render. */
export function useScenarioAnalysis(
  holdings: { holdings: ScenarioHoldingInput[]; cash: number } | null,
  benchmark: string,
  riskFreeRate: number,
) {
  const signature = holdings
    ? `${holdings.holdings.map((h) => `${h.ticker}:${h.dollar_value.toFixed(2)}`).sort().join(",")}|${holdings.cash.toFixed(2)}`
    : null;
  return useQuery({
    queryKey: ["scenario", "baseline", signature, benchmark, riskFreeRate],
    queryFn: () => analyzeScenario({ holdings: holdings!.holdings, cash: holdings!.cash, benchmark_ticker: benchmark, risk_free_rate: riskFreeRate }),
    enabled: holdings !== null,
    staleTime: 30_000,
    retry: false,
  });
}

/** "Use Smart Invest recommendation" inside Scenario Analysis — reuses the
 * existing `/smart-invest` optimizer call verbatim (default 12-ETF
 * universe, max_sharpe) rather than a second allocation algorithm. */
export function useSmartInvestForScenario() {
  return useMutation({
    mutationFn: (investmentAmount: number) => smartInvest({ investment_amount: investmentAmount, strategy: "max_sharpe" }),
  });
}

export function useAssistantStatus() {
  return useQuery({
    queryKey: ["assistant", "status"],
    queryFn: getAssistantStatus,
    staleTime: 60_000,
    retry: false,
  });
}
