import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { smartInvest } from "../../lib/analyticsApi";
import type { Strategy, SmartInvestResponse } from "../../lib/analyticsApi";
import { usePortfolioSummary, useQuotes, usePortfolioRisk } from "../../lib/queries";
import { computeValuation } from "../../lib/valuation";
import { placeOrder } from "../../lib/portfolioApi";
import { ApiError } from "../../lib/apiClient";
import { ETF_UNIVERSE } from "../../lib/catalog";
import { money, percent } from "../../lib/format";
import { StatTile } from "../StatTile";
import { Button } from "../Button";
import { FilterGroup } from "../FilterGroup";
import { SectionEyebrow } from "./SectionEyebrow";

const TRAINED_TICKERS = ETF_UNIVERSE.filter((e) => e.hasModel).map((e) => e.ticker);

type RiskProfile = "conservative" | "moderate" | "aggressive";
const PROFILES: { value: RiskProfile; label: string }[] = [
  { value: "conservative", label: "Conservative" },
  { value: "moderate", label: "Moderate" },
  { value: "aggressive", label: "Aggressive" },
];

type Horizon = "short" | "medium" | "long";
const HORIZONS: { value: Horizon; label: string }[] = [
  { value: "short", label: "Short (<3y)" },
  { value: "medium", label: "Medium (3–7y)" },
  { value: "long", label: "Long (7y+)" },
];

/** Maps a risk profile + horizon to one of the optimizer's real strategies
 * — no new backend concept, just a documented choice among strategies that
 * already exist (`backend/optimizer.py`). A short horizon always prioritizes
 * capital preservation regardless of stated risk appetite. */
function strategyFor(profile: RiskProfile, horizon: Horizon): Strategy {
  if (horizon === "short") return "min_volatility";
  if (profile === "conservative") return "min_volatility";
  if (profile === "aggressive") return "max_sharpe";
  return "risk_parity";
}

const INPUT_CLASS =
  "rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10";

interface ProposedOrder {
  ticker: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  value: number;
}

export function SmartInvestPanel() {
  const [profile, setProfile] = useState<RiskProfile>("moderate");
  const [horizon, setHorizon] = useState<Horizon>("medium");
  const [investmentAmount, setInvestmentAmount] = useState("100000");
  const [riskFreeRate, setRiskFreeRate] = useState("2");
  const [tickers, setTickers] = useState<string[]>(TRAINED_TICKERS);
  const [reviewing, setReviewing] = useState(false);
  const [executionLog, setExecutionLog] = useState<{ ticker: string; side: string; status: string }[] | null>(null);

  const queryClient = useQueryClient();
  const summary = usePortfolioSummary();
  const positionTickers = useMemo(() => summary.data?.positions.map((p) => p.ticker) ?? [], [summary.data]);
  const currentRisk = usePortfolioRisk();

  const strategy = strategyFor(profile, horizon);
  const mutation = useMutation({ mutationFn: smartInvest, retry: false });

  const allQuoteTickers = useMemo(
    () => Array.from(new Set([...tickers, ...positionTickers])),
    [tickers, positionTickers],
  );
  const quotes = useQuotes(allQuoteTickers);

  const currentValuation = useMemo(() => {
    if (!summary.data || !quotes.data) return null;
    return computeValuation(summary.data.positions, quotes.data.quotes, summary.data.account.cash, summary.data.account.initial_cash);
  }, [summary.data, quotes.data]);

  function toggleTicker(ticker: string) {
    setTickers((prev) => (prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker]));
  }

  function handleGenerate() {
    const amount = Number(investmentAmount);
    const rf = Number(riskFreeRate);
    setReviewing(false);
    setExecutionLog(null);
    mutation.mutate({
      tickers,
      strategy,
      risk_free_rate: Number.isFinite(rf) ? rf / 100 : 0.02,
      investment_amount: Number.isFinite(amount) && amount > 0 ? amount : undefined,
    });
  }

  const data: SmartInvestResponse | undefined = mutation.data;

  const proposedOrders: ProposedOrder[] = useMemo(() => {
    if (!data || !quotes.data || !currentValuation) return [];
    const amount = data.investment_amount ?? (Number(investmentAmount) || 0);
    const orders: ProposedOrder[] = [];
    for (const alloc of data.allocations) {
      const quote = quotes.data.quotes[alloc.ticker];
      if (!quote) continue;
      const targetValue = (alloc.weight_percent / 100) * amount;
      const currentHolding = currentValuation.holdings.find((h) => h.ticker === alloc.ticker);
      const currentValue = currentHolding?.marketValue ?? 0;
      const deltaValue = targetValue - currentValue;
      if (Math.abs(deltaValue) < 10) continue; // dust threshold
      const quantity = Math.abs(deltaValue) / quote.price;
      orders.push({
        ticker: alloc.ticker,
        side: deltaValue > 0 ? "BUY" : "SELL",
        quantity,
        price: quote.price,
        value: Math.abs(deltaValue),
      });
    }
    // Sells first to free up cash before buys execute.
    return orders.sort((a, b) => (a.side === "SELL" ? -1 : 1) - (b.side === "SELL" ? -1 : 1));
  }, [data, quotes.data, currentValuation, investmentAmount]);

  const executeMutation = useMutation({
    mutationFn: async () => {
      const results: { ticker: string; side: string; status: string }[] = [];
      for (const order of proposedOrders) {
        try {
          const placed = await placeOrder({
            ticker: order.ticker,
            side: order.side,
            quantity: Number(order.quantity.toFixed(4)),
            order_type: "MARKET",
          });
          results.push({ ticker: order.ticker, side: order.side, status: placed.status });
        } catch (err) {
          results.push({
            ticker: order.ticker, side: order.side,
            status: err instanceof ApiError ? (err.detail ?? "ERROR") : "ERROR",
          });
        }
      }
      return results;
    },
    onSuccess: (results) => {
      setExecutionLog(results);
      setReviewing(false);
      void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["portfolio", "equity-curve"] });
      void queryClient.invalidateQueries({ queryKey: ["risk", "portfolio"] });
    },
  });

  const errorMessage =
    mutation.error instanceof ApiError ? (mutation.error.detail ?? mutation.error.message) : mutation.isError ? "Could not generate a recommendation." : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-md border border-line p-4">
        <SectionEyebrow>Configuration</SectionEyebrow>
        <div className="mb-1 mt-1 text-sm font-bold text-ink">Smart Invest</div>
        <p className="mb-4 text-xs text-ink-faint">
          A guided allocation workflow built on the same LSTM forecasting + mean-variance
          optimization engine as Portfolio Optimizer — your risk profile and horizon choose which
          existing strategy runs. Proposing an allocation never trades on its own; you review and
          confirm every order before it executes.
        </p>

        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Investment amount ($)
            <input
              type="number" min="0" step="1000" value={investmentAmount}
              onChange={(e) => setInvestmentAmount(e.target.value)}
              className={`w-36 font-mono ${INPUT_CLASS}`}
            />
          </label>
          <div className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Risk profile
            <FilterGroup value={profile} onChange={setProfile} options={PROFILES} />
          </div>
          <div className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Horizon
            <FilterGroup value={horizon} onChange={setHorizon} options={HORIZONS} />
          </div>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Risk-free rate (%)
            <input
              type="number" min="0" step="0.25" value={riskFreeRate}
              onChange={(e) => setRiskFreeRate(e.target.value)}
              className={`w-24 font-mono ${INPUT_CLASS}`}
            />
          </label>
          <Button onClick={handleGenerate} disabled={mutation.isPending || tickers.length === 0}>
            {mutation.isPending ? "Generating…" : "Generate Recommendation"}
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap gap-1.5">
          {ETF_UNIVERSE.filter((e) => e.hasModel).map((e) => (
            <button
              key={e.ticker}
              type="button"
              onClick={() => toggleTicker(e.ticker)}
              className={`rounded px-2.5 py-1 text-xs font-mono font-semibold ${
                tickers.includes(e.ticker) ? "border-accent-strong bg-ink-strong text-white" : "border border-line-strong text-ink-muted hover:bg-surface-alt"
              }`}
            >
              {e.ticker}
            </button>
          ))}
        </div>

        <p className="mt-3 text-xs text-ink-faint">
          Strategy selected from your inputs: <span className="font-semibold text-ink">{strategy.replace("_", " ")}</span>
        </p>
        {errorMessage && <p role="alert" className="mt-3 rounded bg-down-soft px-3 py-2 text-sm text-down">{errorMessage}</p>}
      </div>

      {data && (
        <>
          <SectionEyebrow>Recommendation</SectionEyebrow>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded bg-accent-soft px-2 py-1 font-semibold text-ink">
              Strategy: {strategy.replace("_", " ")}
            </span>
            <span className="rounded bg-surface-alt px-2 py-1 font-semibold text-ink-muted">
              Risk profile: {PROFILES.find((p) => p.value === profile)?.label}
            </span>
            <span className="rounded bg-surface-alt px-2 py-1 font-semibold text-ink-muted">
              Horizon: {HORIZONS.find((h) => h.value === horizon)?.label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Expected Return (forecast-based)" value={percent(data.portfolio_metrics.expected_annual_return_capped, 1)} />
            <StatTile label="Volatility (forecast-based)" value={percent(data.portfolio_metrics.annual_volatility_percent, 1)} />
            <StatTile label="Sharpe Ratio" value={data.portfolio_metrics.sharpe_ratio.toFixed(2)} />
            <StatTile label="Diversification" value={data.portfolio_metrics.diversification_score.toFixed(2)} />
          </div>

          <SectionEyebrow>Why this strategy?</SectionEyebrow>
          <div className="rounded-md border border-line p-4 text-sm text-ink-muted">
            Based on a <span className="font-semibold text-ink">{PROFILES.find((p) => p.value === profile)?.label}</span> risk
            profile and <span className="font-semibold text-ink">{HORIZONS.find((h) => h.value === horizon)?.label.split(" ")[0]}</span>-term
            horizon, this recommendation uses <span className="font-semibold text-ink">{strategy.replace("_", " ")}</span> optimization
            over historical covariance and LSTM-forecasted 22-day returns for {tickers.length} selected ETFs.
          </div>

          <SectionEyebrow>Proposed allocation</SectionEyebrow>
          <div className="rounded-md border border-line p-4">
            <div className="flex flex-col gap-2">
              {data.allocations.map((a) => (
                <div key={a.ticker} className="flex flex-col gap-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-semibold text-ink">{a.ticker}</span>
                    <span className="text-ink-muted">
                      {percent(a.weight_percent, 1)}
                      {a.amount != null && ` · ${money(a.amount)}`}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
                    <div
                      className="h-full rounded-full bg-accent-strong"
                      style={{ width: `${Math.min(a.weight_percent, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-line">
            <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
              Current portfolio vs. proposed allocation
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-2 font-semibold">Ticker</th>
                    <th className="px-4 py-2 font-semibold">Current Weight</th>
                    <th className="px-4 py-2 font-semibold">Proposed Weight</th>
                    <th className="px-4 py-2 font-semibold">Proposed Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft font-mono">
                  {data.allocations.map((a) => {
                    const current = currentValuation?.holdings.find((h) => h.ticker === a.ticker);
                    return (
                      <tr key={a.ticker}>
                        <td className="px-4 py-2.5 font-sans font-semibold text-ink">{a.ticker}</td>
                        <td className="px-4 py-2.5 text-ink-muted">{current?.weight != null ? percent(current.weight, 1) : "0.0%"}</td>
                        <td className="px-4 py-2.5">{percent(a.weight_percent, 1)}</td>
                        <td className="px-4 py-2.5">{a.amount != null ? money(a.amount) : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {currentRisk.data?.status === "ok" && (
              <div className="border-t border-line-soft px-4 py-2.5 text-xs text-ink-faint">
                Current portfolio volatility (1y realized, {currentRisk.data.lookback_days}d): {percent(currentRisk.data.volatility_pct ?? 0, 1)}
                {" · "}Proposed portfolio volatility (LSTM-forecast-based): {percent(data.portfolio_metrics.annual_volatility_percent, 1)}
                {" — these use different methodologies and are not directly comparable on a like-for-like basis."}
              </div>
            )}
          </div>

          {!reviewing && !executionLog && (
            <div>
              <Button onClick={() => setReviewing(true)} disabled={proposedOrders.length === 0}>
                Use this allocation → Generate Proposed Orders
              </Button>
              {proposedOrders.length === 0 && (
                <p className="mt-2 text-xs text-ink-faint">Your current holdings already match this allocation closely.</p>
              )}
            </div>
          )}

          {reviewing && (
            <div className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Review proposed orders ({proposedOrders.length})
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[480px] text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="px-4 py-2 font-semibold">Ticker</th>
                      <th className="px-4 py-2 font-semibold">Side</th>
                      <th className="px-4 py-2 font-semibold">Est. Qty</th>
                      <th className="px-4 py-2 font-semibold">Est. Price</th>
                      <th className="px-4 py-2 font-semibold">Est. Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line-soft font-mono">
                    {proposedOrders.map((o) => (
                      <tr key={o.ticker}>
                        <td className="px-4 py-2.5 font-sans font-semibold text-ink">{o.ticker}</td>
                        <td className={`px-4 py-2.5 ${o.side === "BUY" ? "text-up" : "text-down"}`}>{o.side}</td>
                        <td className="px-4 py-2.5">{o.quantity.toFixed(2)}</td>
                        <td className="px-4 py-2.5">{money(o.price, 2)}</td>
                        <td className="px-4 py-2.5">{money(o.value, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center gap-3 border-t border-line px-4 py-3">
                <Button onClick={() => executeMutation.mutate()} disabled={executeMutation.isPending}>
                  {executeMutation.isPending ? "Executing…" : "Confirm & Execute Paper Trades"}
                </Button>
                <button
                  onClick={() => setReviewing(false)}
                  disabled={executeMutation.isPending}
                  className="text-sm font-semibold text-ink-muted hover:text-ink"
                >
                  Cancel
                </button>
                <span className="ml-auto text-xs text-ink-faint">
                  Orders execute one by one against your real simulated account via the existing order engine.
                </span>
              </div>
            </div>
          )}

          {executionLog && (
            <div className="rounded-md border border-line p-4">
              <div className="mb-3 text-sm font-bold text-ink">Execution result</div>
              <div className="flex flex-col gap-1.5 text-sm">
                {executionLog.map((r, i) => (
                  <div key={i} className="flex items-center justify-between font-mono">
                    <span>{r.side} {r.ticker}</span>
                    <span className={r.status === "FILLED" ? "text-up" : "text-down"}>{r.status}</span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs text-ink-faint">
                Your portfolio, dashboard, and risk metrics now reflect these trades.
              </p>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {data.top_picks.map((t) => (
              <span key={t} className="rounded bg-accent-soft px-2 py-1 font-mono text-xs font-semibold text-ink">{t}</span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
