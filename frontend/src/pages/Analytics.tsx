import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { smartInvest, getEfficientFrontier } from "../lib/analyticsApi";
import type { Strategy } from "../lib/analyticsApi";
import { ApiError } from "../lib/apiClient";
import { money, percent, signedPercent } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { Button } from "../components/Button";
import { ModelEvaluationPanel } from "../components/analytics/ModelEvaluationPanel";
import { BacktestPanel } from "../components/analytics/BacktestPanel";
import { SmartInvestPanel } from "../components/analytics/SmartInvestPanel";
import { EfficientFrontierChart } from "../components/analytics/EfficientFrontierChart";
import { SectionEyebrow } from "../components/analytics/SectionEyebrow";
import { MarketRegimePanel } from "../components/analytics/MarketRegimePanel";
import { ModelComparisonPanel } from "../components/analytics/ModelComparisonPanel";

type AnalyticsTab = "optimizer" | "smart-invest" | "evaluation" | "comparison" | "regime" | "backtest";

const TABS: { value: AnalyticsTab; label: string }[] = [
  { value: "optimizer", label: "Portfolio Optimizer" },
  { value: "smart-invest", label: "Smart Invest" },
  { value: "evaluation", label: "Model Evaluation" },
  { value: "comparison", label: "Model Comparison" },
  { value: "regime", label: "Market Regime" },
  { value: "backtest", label: "Backtesting" },
];

const STRATEGIES: { value: Strategy; label: string }[] = [
  { value: "max_sharpe", label: "Max Sharpe" },
  { value: "min_volatility", label: "Min Volatility" },
  { value: "risk_parity", label: "Risk Parity" },
  { value: "equal_weight", label: "Equal Weight" },
];

const RECOMMENDATION_TONE: Record<string, string> = {
  "Strong Buy": "bg-up-soft text-up",
  Buy: "bg-up-soft text-up",
  Hold: "bg-surface-alt text-ink-muted",
  Light: "bg-surface-alt text-ink-muted",
  Avoid: "bg-down-soft text-down",
};

const INPUT_CLASS =
  "rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10";


/**
 * Thin UI over the backend's existing `/smart-invest` — real LSTM return
 * forecasts + mean-variance optimization over real historical covariance
 * (`backend/forecaster.py` / `backend/optimizer.py`). No recommendation
 * here is computed in React; every allocation, weight and metric is exactly
 * what the backend returned.
 */
function PortfolioOptimizerTab() {
  const [strategy, setStrategy] = useState<Strategy>("max_sharpe");
  const [riskFreeRate, setRiskFreeRate] = useState("5");
  const [investmentAmount, setInvestmentAmount] = useState("");

  const mutation = useMutation({
    mutationFn: smartInvest,
    retry: false,
  });
  const frontierMutation = useMutation({
    mutationFn: getEfficientFrontier,
    retry: false,
  });

  function handleRun() {
    const rf = Number(riskFreeRate);
    const rfDecimal = Number.isFinite(rf) ? rf / 100 : 0.05;
    const amount = investmentAmount.trim() ? Number(investmentAmount) : undefined;
    mutation.mutate({
      strategy,
      risk_free_rate: rfDecimal,
      investment_amount: amount && Number.isFinite(amount) && amount > 0 ? amount : undefined,
    });
    frontierMutation.mutate({ risk_free_rate: rfDecimal });
  }

  const errorMessage =
    mutation.error instanceof ApiError
      ? (mutation.error.detail ?? mutation.error.message)
      : mutation.isError
        ? "Could not run the analysis."
        : null;

  const data = mutation.data;
  const frontier = frontierMutation.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-md border border-line p-4">
        <SectionEyebrow>Configuration</SectionEyebrow>
        <div className="mb-3 mt-1 text-sm font-bold text-ink">Portfolio optimizer</div>
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Strategy
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as Strategy)}
              className={INPUT_CLASS}
            >
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Risk-free rate (%)
            <input
              type="number"
              min="0"
              step="0.25"
              value={riskFreeRate}
              onChange={(e) => setRiskFreeRate(e.target.value)}
              className={`w-32 font-mono ${INPUT_CLASS}`}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Investment amount ($, optional)
            <input
              type="number"
              min="0"
              step="1000"
              placeholder="e.g. 10000"
              value={investmentAmount}
              onChange={(e) => setInvestmentAmount(e.target.value)}
              className={`w-48 font-mono ${INPUT_CLASS}`}
            />
          </label>
          <Button onClick={handleRun} disabled={mutation.isPending}>
            {mutation.isPending ? "Running…" : "Run analysis"}
          </Button>
        </div>
        <p className="mt-3 text-xs text-ink-faint">
          Runs the existing forecasting + mean-variance optimization engine over the default ETF
          universe, fetching fresh historical data for each ticker. This can take up to a minute.
        </p>
        {errorMessage && (
          <p role="alert" className="mt-3 rounded bg-down-soft px-3 py-2 text-sm text-down">
            {errorMessage}
          </p>
        )}
      </div>

      {data && (
        <>
          <div>
            <SectionEyebrow>Optimization Results</SectionEyebrow>
            <p className="mt-1 text-xs text-ink-faint">
              Expected return is the LSTM-forecasted 22-day return, annualized; volatility and Sharpe
              use real historical covariance for the same universe.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile
              label="Expected Annual Return"
              value={percent(data.portfolio_metrics.expected_annual_return_capped, 1)}
            />
            <StatTile
              label="Annual Volatility"
              value={percent(data.portfolio_metrics.annual_volatility_percent, 1)}
            />
            <StatTile label="Sharpe Ratio" value={data.portfolio_metrics.sharpe_ratio.toFixed(2)} />
            <StatTile
              label="Diversification"
              value={data.portfolio_metrics.diversification_score.toFixed(2)}
            />
          </div>

          <SectionEyebrow>Allocation</SectionEyebrow>
          <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
            <div className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Allocations — {STRATEGIES.find((s) => s.value === data.strategy_used)?.label ?? data.strategy_used}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="px-4 py-2 font-semibold">Ticker</th>
                      <th className="px-4 py-2 font-semibold">Weight</th>
                      {data.investment_amount != null && (
                        <th className="px-4 py-2 font-semibold">Amount</th>
                      )}
                      <th className="px-4 py-2 font-semibold">Predicted Return</th>
                      <th className="px-4 py-2 font-semibold">Volatility</th>
                      <th className="px-4 py-2 font-semibold">YTD</th>
                      <th className="px-4 py-2 font-semibold">Signal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line-soft font-mono">
                    {data.allocations.map((a) => (
                      <tr key={a.ticker}>
                        <td className="px-4 py-2.5 font-sans">
                          <span className="font-semibold text-ink">{a.ticker}</span>
                          <span className="ml-2 text-xs text-ink-faint">{a.name}</span>
                        </td>
                        <td className="px-4 py-2.5">{percent(a.weight_percent, 1)}</td>
                        {data.investment_amount != null && (
                          <td className="px-4 py-2.5">{a.amount != null ? money(a.amount) : "—"}</td>
                        )}
                        <td className="px-4 py-2.5">{signedPercent(a.predicted_return_capped, 1)}</td>
                        <td className="px-4 py-2.5">{percent(a.historical_volatility * 100, 1)}</td>
                        <td className="px-4 py-2.5">{signedPercent(a.ytd_return, 1)}</td>
                        <td className="px-4 py-2.5 font-sans">
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-semibold ${
                              RECOMMENDATION_TONE[a.recommendation] ?? "bg-surface-alt text-ink-muted"
                            }`}
                          >
                            {a.recommendation}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex flex-col gap-6">
              <div className="rounded-md border border-line p-4">
                <div className="mb-3 text-sm font-bold text-ink">Geographic allocation</div>
                <div className="flex flex-col gap-2">
                  {data.geographic_allocation.map((g) => (
                    <div key={g.region} className="flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs text-ink-muted">
                        <span>{g.region}</span>
                        <span className="font-mono">{percent(g.allocation_percent, 1)}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
                        <div
                          className="h-full rounded-full bg-accent-strong"
                          style={{ width: `${Math.min(g.allocation_percent, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-line p-4">
                <div className="mb-2 text-sm font-bold text-ink">Top picks</div>
                <div className="flex flex-wrap gap-2">
                  {data.top_picks.map((t) => (
                    <span key={t} className="rounded bg-accent-soft px-2 py-1 font-mono text-xs font-semibold text-ink">
                      {t}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-line p-4">
                <div className="mb-2 text-sm font-bold text-ink">Summary</div>
                <pre className="whitespace-pre-wrap font-sans text-sm text-ink-muted">
                  {data.recommendation_summary}
                </pre>
              </div>
            </div>
          </div>

          <SectionEyebrow>Efficient Frontier</SectionEyebrow>
          <div className="rounded-md border border-line p-4">
            {frontierMutation.isPending ? (
              <div className="flex h-[280px] items-center justify-center text-sm text-ink-muted">
                Computing frontier…
              </div>
            ) : frontier ? (
              <>
                <EfficientFrontierChart
                  points={frontier.returns.map((r, i) => ({ return: r, volatility: frontier.volatilities[i] }))}
                  maxSharpe={{ return: frontier.max_sharpe_return, volatility: frontier.max_sharpe_volatility }}
                  minVolatility={{ return: frontier.min_vol_return, volatility: frontier.min_vol_volatility }}
                  selected={{
                    return: data.portfolio_metrics.expected_annual_return_capped / 100,
                    volatility: data.portfolio_metrics.annual_volatility_percent / 100,
                  }}
                />
                <div className="mt-3 flex flex-wrap gap-4 text-xs text-ink-muted">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-down" /> Selected strategy
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-ink-strong" /> Max Sharpe
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-up" /> Min volatility
                  </span>
                </div>
              </>
            ) : (
              <div className="flex h-[280px] items-center justify-center text-sm text-ink-faint">
                No frontier data available.
              </div>
            )}
            <p className="mt-3 text-xs text-ink-faint">
              Each point on the line is a real optimized portfolio (`compute_efficient_frontier`) for a
              target return over the same LSTM forecasts and historical covariance — not an
              interpolation.
            </p>
          </div>

          <details className="rounded-md border border-line p-4 text-sm">
            <summary className="cursor-pointer font-bold text-ink">Methodology &amp; assumptions</summary>
            <ul className="mt-3 flex flex-col gap-2 text-xs text-ink-muted">
              <li className="flex gap-2">
                <span className="text-ink-faint">•</span>
                <span>
                  Expected returns come from the per-ticker LSTM 22-day-return forecasts
                  (`backend/forecaster.py`), annualized and capped at ±200%/year for extreme outputs.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-faint">•</span>
                <span>Covariance is computed from real historical daily returns for the same universe, annualized (×252 trading days).</span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-faint">•</span>
                <span>
                  Weights are chosen by mean-variance optimization for the selected strategy — Max
                  Sharpe, Min Volatility, Risk Parity, or Equal Weight — never hand-picked.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-faint">•</span>
                <span>This is a point-in-time analytical result, not a guarantee of future performance.</span>
              </li>
            </ul>
          </details>
        </>
      )}
    </div>
  );
}

export function AnalyticsPage() {
  const [tab, setTab] = useState<AnalyticsTab>("optimizer");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-ink">Analytics</h1>
        <p className="mt-1 text-xs text-ink-faint">Research terminal — forecasting, optimization and historical simulation over the app's real ETF universe.</p>
      </div>

      <div className="grid grid-cols-2 gap-1 rounded-md border border-line-strong bg-surface p-1 sm:grid-cols-3 lg:inline-grid lg:grid-cols-6">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            aria-current={tab === t.value ? "page" : undefined}
            className={`rounded px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-strong/40 ${
              tab === t.value
                ? "bg-ink-strong text-white"
                : "text-ink-muted hover:bg-surface-alt hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "optimizer" && <PortfolioOptimizerTab />}
      {tab === "smart-invest" && <SmartInvestPanel />}
      {tab === "evaluation" && <ModelEvaluationPanel />}
      {tab === "comparison" && <ModelComparisonPanel />}
      {tab === "regime" && <MarketRegimePanel />}
      {tab === "backtest" && <BacktestPanel />}
    </div>
  );
}
