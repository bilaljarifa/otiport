import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  usePortfolioSummary, useQuotes, useScenarioAnalysis, useSmartInvestForScenario,
} from "../lib/queries";
import { computeValuation } from "../lib/valuation";
import type { Valuation } from "../lib/valuation";
import { analyzeScenario } from "../lib/scenarioApi";
import type { ScenarioResult } from "../lib/scenarioApi";
import { computeProposedOrders } from "../lib/orderPlanning";
import { ApiError } from "../lib/apiClient";
import { ETF_UNIVERSE } from "../lib/catalog";
import { money, percent, signedPercent } from "../lib/format";
import { Button } from "../components/Button";
import { FilterGroup } from "../components/FilterGroup";
import { QueryState } from "../components/QueryState";
import { ProposedOrdersReview } from "../components/analytics/ProposedOrdersReview";

type Mode = "rebalance" | "shock";
const MODES: { value: Mode; label: string }[] = [
  { value: "rebalance", label: "Rebalance Allocation" },
  { value: "shock", label: "Price Shock" },
];

const BENCHMARKS: { value: string; label: string }[] = [
  { value: "SPY", label: "SPY" },
  { value: "QQQ", label: "QQQ" },
];

const HOLDABLE_TICKERS = ETF_UNIVERSE.map((e) => e.ticker);

/** Rebalance scenario: any ticker the user has explicitly assigned a target
 * weight keeps that target; every other ticker keeps its CURRENT dollar
 * value unchanged. The difference is funded from/returned to cash — total
 * portfolio equity is conserved, exactly like Smart Invest's own model. */
function buildRebalanceHoldings(valuation: Valuation, scenarioWeights: Record<string, number>) {
  const totalEquity = valuation.equity;
  const currentByTicker: Record<string, number> = {};
  for (const h of valuation.holdings) if (h.marketValue != null) currentByTicker[h.ticker] = h.marketValue;

  const allTickers = new Set([...Object.keys(currentByTicker), ...Object.keys(scenarioWeights)]);
  let cashDelta = 0;
  const holdings: { ticker: string; dollar_value: number }[] = [];
  for (const ticker of allTickers) {
    const currentValue = currentByTicker[ticker] ?? 0;
    if (ticker in scenarioWeights) {
      const targetValue = Math.max((scenarioWeights[ticker] / 100) * totalEquity, 0);
      holdings.push({ ticker, dollar_value: targetValue });
      cashDelta += currentValue - targetValue;
    } else if (currentValue > 0) {
      holdings.push({ ticker, dollar_value: currentValue });
    }
  }
  return { holdings, cash: Math.max(valuation.cash + cashDelta, 0) };
}

/** Price-shock scenario: quantities are untouched (no trading happened);
 * only the shocked ticker's price — and therefore its value and every
 * weight — changes. Cash is untouched. */
function buildShockHoldings(valuation: Valuation, shockTicker: string, shockedPrice: number) {
  const holdings = valuation.holdings
    .filter((h) => h.marketValue != null)
    .map((h) => ({
      ticker: h.ticker,
      dollar_value: h.ticker === shockTicker ? Math.max(h.quantity * shockedPrice, 0) : (h.marketValue as number),
    }));
  return { holdings, cash: valuation.cash };
}

function weightOf(result: ScenarioResult | undefined, ticker: string): number {
  return result?.positions.find((p) => p.ticker === ticker)?.weight_pct ?? 0;
}

export function ScenarioAnalysisPage() {
  const [mode, setMode] = useState<Mode>("rebalance");
  const [scenarioWeights, setScenarioWeights] = useState<Record<string, number>>({});
  const [tickerToAdd, setTickerToAdd] = useState("");
  const [shockTicker, setShockTicker] = useState("");
  const [shockPct, setShockPct] = useState("-10");
  const [benchmark, setBenchmark] = useState("SPY");
  const [riskFreeRate, setRiskFreeRate] = useState("2");
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);
  const [reviewing, setReviewing] = useState(false);

  const summary = usePortfolioSummary();
  const positionTickers = useMemo(() => summary.data?.positions.map((p) => p.ticker) ?? [], [summary.data]);
  const allQuoteTickers = useMemo(
    () => Array.from(new Set([...positionTickers, ...Object.keys(scenarioWeights)])),
    [positionTickers, scenarioWeights],
  );
  const quotes = useQuotes(allQuoteTickers);

  const valuation = useMemo(() => {
    if (!summary.data || !quotes.data) return null;
    return computeValuation(summary.data.positions, quotes.data.quotes, summary.data.account.cash, summary.data.account.initial_cash);
  }, [summary.data, quotes.data]);

  const rf = Number(riskFreeRate);
  const riskFreeRateFraction = Number.isFinite(rf) ? rf / 100 : 0.02;

  // "Current" baseline, computed through the exact same endpoint/methodology
  // as the scenario itself, cached and only recomputed when the real
  // portfolio, benchmark, or risk-free input actually changes.
  const currentHoldingsForApi = useMemo(() => {
    if (!valuation) return null;
    return {
      holdings: valuation.holdings.filter((h) => h.marketValue != null).map((h) => ({ ticker: h.ticker, dollar_value: h.marketValue as number })),
      cash: valuation.cash,
    };
  }, [valuation]);
  const currentAnalysis = useScenarioAnalysis(currentHoldingsForApi, benchmark, riskFreeRateFraction);

  const scenarioMutation = useMutation({
    mutationFn: analyzeScenario,
    onSuccess: (data) => setScenarioResult(data),
  });

  function handleAnalyze() {
    if (!valuation) return;
    setReviewing(false);
    let built: { holdings: { ticker: string; dollar_value: number }[]; cash: number };
    if (mode === "rebalance") {
      built = buildRebalanceHoldings(valuation, scenarioWeights);
    } else {
      const price = quotes.data?.quotes[shockTicker]?.price;
      const pct = Number(shockPct);
      if (!price || !Number.isFinite(pct)) return;
      built = buildShockHoldings(valuation, shockTicker, price * (1 + pct / 100));
    }
    scenarioMutation.mutate({ holdings: built.holdings, cash: built.cash, benchmark_ticker: benchmark, risk_free_rate: riskFreeRateFraction });
  }

  function handleReset() {
    setScenarioWeights({});
    setShockTicker("");
    setShockPct("-10");
    setScenarioResult(null);
    setReviewing(false);
  }

  const smartInvestFill = useSmartInvestForScenario();
  function handleUseOptimized() {
    if (!valuation) return;
    smartInvestFill.mutate(valuation.equity, {
      onSuccess: (data) => {
        const next: Record<string, number> = {};
        for (const a of data.allocations) next[a.ticker] = a.weight_percent;
        setScenarioWeights(next);
        setScenarioResult(null);
      },
    });
  }

  const proposedOrders = useMemo(() => {
    if (mode !== "rebalance" || !scenarioResult || !valuation || !quotes.data) return [];
    const currentByTicker: Record<string, number> = {};
    for (const h of valuation.holdings) if (h.marketValue != null) currentByTicker[h.ticker] = h.marketValue;
    const priceByTicker: Record<string, number> = {};
    for (const [t, q] of Object.entries(quotes.data.quotes)) priceByTicker[t] = q.price;
    const targets = scenarioResult.positions.map((p) => ({ ticker: p.ticker, targetValue: p.market_value }));
    return computeProposedOrders(targets, currentByTicker, priceByTicker);
  }, [mode, scenarioResult, valuation, quotes.data]);

  const allDisplayedTickers = useMemo(() => {
    const set = new Set<string>();
    for (const h of valuation?.holdings ?? []) set.add(h.ticker);
    for (const p of scenarioResult?.positions ?? []) set.add(p.ticker);
    return Array.from(set).sort();
  }, [valuation, scenarioResult]);

  const impactNotes = useMemo(() => {
    if (!currentAnalysis.data || !scenarioResult) return [];
    const notes: string[] = [];
    const cur = currentAnalysis.data;
    const scen = scenarioResult;
    for (const ticker of allDisplayedTickers) {
      const before = weightOf(cur, ticker);
      const after = weightOf(scen, ticker);
      const delta = after - before;
      if (Math.abs(delta) >= 0.5) {
        notes.push(`${ticker} exposure ${delta > 0 ? "increases" : "decreases"} by ${Math.abs(delta).toFixed(1)} percentage points (${before.toFixed(1)}% → ${after.toFixed(1)}%).`);
      }
    }
    if (cur.volatility_pct != null && scen.volatility_pct != null) {
      notes.push(`Portfolio volatility changes from ${cur.volatility_pct.toFixed(1)}% to ${scen.volatility_pct.toFixed(1)}%.`);
    }
    if (cur.sharpe_ratio != null && scen.sharpe_ratio != null) {
      notes.push(`Sharpe ratio changes from ${cur.sharpe_ratio.toFixed(2)} to ${scen.sharpe_ratio.toFixed(2)}.`);
    }
    if (cur.diversification_score != null && scen.diversification_score != null) {
      notes.push(`Diversification score changes from ${cur.diversification_score.toFixed(2)} to ${scen.diversification_score.toFixed(2)}.`);
    }
    if (cur.max_drawdown_pct != null && scen.max_drawdown_pct != null) {
      notes.push(`Max drawdown (1y basis) changes from ${cur.max_drawdown_pct.toFixed(1)}% to ${scen.max_drawdown_pct.toFixed(1)}%.`);
    }
    return notes;
  }, [currentAnalysis.data, scenarioResult, allDisplayedTickers]);

  const scenarioError =
    scenarioMutation.error instanceof ApiError ? (scenarioMutation.error.detail ?? scenarioMutation.error.message)
      : scenarioMutation.isError ? "Could not analyze this scenario." : null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-ink">Scenario Analysis</h1>
        <p className="mt-1 text-xs text-ink-faint">
          Explore hypothetical portfolio changes without affecting your real account. Nothing here
          is saved or traded until you explicitly confirm proposed orders in Step 4.
        </p>
      </div>

      <QueryState isLoading={summary.isLoading || quotes.isLoading} isError={summary.isError} error={summary.error} onRetry={() => void summary.refetch()}>
        {valuation && (
          <>
            <section className="rounded-md border border-line p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-bold text-ink">
                <StepBadge n={1} /> Choose scenario
              </div>
              <div className="flex flex-wrap items-end gap-4">
                <FilterGroup value={mode} onChange={(v) => { setMode(v); setScenarioResult(null); setReviewing(false); }} options={MODES} />
                <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                  Benchmark
                  <FilterGroup value={benchmark} onChange={setBenchmark} options={BENCHMARKS} />
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                  Risk-free rate (%)
                  <input type="number" min="0" step="0.25" value={riskFreeRate} onChange={(e) => setRiskFreeRate(e.target.value)}
                    className="w-24 rounded border border-line-strong bg-surface px-3 py-2 text-sm font-mono text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10" />
                </label>
              </div>

              {mode === "rebalance" ? (
                <div className="mt-4">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <select value={tickerToAdd} onChange={(e) => setTickerToAdd(e.target.value)}
                      className="rounded border border-line-strong bg-surface px-2 py-1.5 text-xs font-mono text-ink">
                      <option value="">+ Add ticker…</option>
                      {HOLDABLE_TICKERS.filter((t) => !allDisplayedTickers.includes(t) || !(t in scenarioWeights)).map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => { if (tickerToAdd) { setScenarioWeights((prev) => ({ ...prev, [tickerToAdd]: 0 })); setTickerToAdd(""); } }}
                      className="rounded border border-line-strong px-2.5 py-1.5 text-xs font-semibold text-ink-muted hover:border-ink hover:text-ink"
                    >
                      Add
                    </button>
                    <Button onClick={handleUseOptimized} disabled={smartInvestFill.isPending}>
                      {smartInvestFill.isPending ? "Loading…" : "Use Smart Invest recommendation"}
                    </Button>
                  </div>
                  <div className="overflow-x-auto rounded-md border border-line">
                    <table className="w-full min-w-[480px] text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                          <th className="px-3 py-2 font-semibold">Ticker</th>
                          <th className="px-3 py-2 font-semibold">Current Weight</th>
                          <th className="px-3 py-2 font-semibold">Scenario Weight (%)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line-soft font-mono">
                        {valuation.holdings.filter((h) => h.marketValue != null).map((h) => (
                          <tr key={h.ticker}>
                            <td className="px-3 py-2 font-sans font-semibold text-ink">{h.ticker}</td>
                            <td className="px-3 py-2 text-ink-muted">{h.weight != null ? percent(h.weight, 1) : "—"}</td>
                            <td className="px-3 py-2">
                              <input
                                type="number" min="0" max="100" step="1"
                                value={scenarioWeights[h.ticker] ?? h.weight ?? 0}
                                onChange={(e) => setScenarioWeights((prev) => ({ ...prev, [h.ticker]: Number(e.target.value) }))}
                                className="w-24 rounded border border-line-strong bg-surface px-2 py-1 text-sm font-mono text-ink outline-none focus:border-ink"
                              />
                            </td>
                          </tr>
                        ))}
                        {Object.keys(scenarioWeights).filter((t) => !valuation.holdings.some((h) => h.ticker === t)).map((ticker) => (
                          <tr key={ticker}>
                            <td className="px-3 py-2 font-sans font-semibold text-ink">{ticker}</td>
                            <td className="px-3 py-2 text-ink-muted">0.0%</td>
                            <td className="px-3 py-2">
                              <input
                                type="number" min="0" max="100" step="1"
                                value={scenarioWeights[ticker] ?? 0}
                                onChange={(e) => setScenarioWeights((prev) => ({ ...prev, [ticker]: Number(e.target.value) }))}
                                className="w-24 rounded border border-line-strong bg-surface px-2 py-1 text-sm font-mono text-ink outline-none focus:border-ink"
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-2 text-xs text-ink-faint">
                    Editing a weight funds the difference from/to cash; every other position's dollar value stays the same.
                  </p>
                </div>
              ) : (
                <div className="mt-4 flex flex-wrap items-end gap-4">
                  <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                    Ticker
                    <select value={shockTicker} onChange={(e) => setShockTicker(e.target.value)}
                      className="w-32 rounded border border-line-strong bg-surface px-3 py-2 text-sm font-mono text-ink">
                      <option value="">Select…</option>
                      {positionTickers.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                    Price change (%)
                    <input type="number" step="1" value={shockPct} onChange={(e) => setShockPct(e.target.value)}
                      className="w-28 rounded border border-line-strong bg-surface px-3 py-2 text-sm font-mono text-ink outline-none focus:border-ink" />
                  </label>
                  {shockTicker && quotes.data?.quotes[shockTicker] && (
                    <p className="text-xs text-ink-faint pb-2">
                      Current: {money(quotes.data.quotes[shockTicker].price, 2)} → Scenario: {money(quotes.data.quotes[shockTicker].price * (1 + (Number(shockPct) || 0) / 100), 2)}
                    </p>
                  )}
                  {positionTickers.length === 0 && <p className="text-sm text-ink-muted">No open positions to shock — place a trade first.</p>}
                </div>
              )}

              <div className="mt-4 flex items-center gap-3">
                <Button onClick={handleAnalyze} disabled={scenarioMutation.isPending || (mode === "shock" && !shockTicker)}>
                  {scenarioMutation.isPending ? "Analyzing…" : "Analyze Impact"}
                </Button>
                <button onClick={handleReset} className="text-sm font-semibold text-ink-muted hover:text-ink">Reset Scenario</button>
              </div>
              {scenarioError && <p role="alert" className="mt-3 rounded bg-down-soft px-3 py-2 text-sm text-down">{scenarioError}</p>}
            </section>

            {scenarioResult && currentAnalysis.data && (
              <>
                <section>
                  <div className="mb-3 flex items-center gap-2 text-sm font-bold text-ink">
                    <StepBadge n={2} /> Impact analysis
                  </div>
                  <div className="overflow-x-auto rounded-md border border-line">
                    <table className="w-full min-w-[560px] text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                          <th className="px-4 py-2 font-semibold"></th>
                          <th className="px-4 py-2 font-semibold">Current</th>
                          <th className="px-4 py-2 font-semibold">Scenario</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line-soft font-mono">
                        <ComparisonRow label="Portfolio Value" current={money(currentAnalysis.data.invested_value + currentAnalysis.data.cash)} scenario={money(scenarioResult.invested_value + scenarioResult.cash)} />
                        <ComparisonRow label="Invested" current={money(currentAnalysis.data.invested_value)} scenario={money(scenarioResult.invested_value)} />
                        <ComparisonRow label="Cash" current={money(currentAnalysis.data.cash)} scenario={money(scenarioResult.cash)} />
                        <ComparisonRow label="Expected Return (model estimate)" current={currentAnalysis.data.expected_return_pct != null ? signedPercent(currentAnalysis.data.expected_return_pct) : "—"} scenario={scenarioResult.expected_return_pct != null ? signedPercent(scenarioResult.expected_return_pct) : "—"} />
                        <ComparisonRow label="Volatility (1y basis)" current={currentAnalysis.data.volatility_pct != null ? percent(currentAnalysis.data.volatility_pct, 1) : "—"} scenario={scenarioResult.volatility_pct != null ? percent(scenarioResult.volatility_pct, 1) : "—"} />
                        <ComparisonRow label="Sharpe Ratio" current={currentAnalysis.data.sharpe_ratio?.toFixed(2) ?? "—"} scenario={scenarioResult.sharpe_ratio?.toFixed(2) ?? "—"} />
                        <ComparisonRow label="Max Drawdown (1y basis)" current={currentAnalysis.data.max_drawdown_pct != null ? signedPercent(currentAnalysis.data.max_drawdown_pct, 1) : "—"} scenario={scenarioResult.max_drawdown_pct != null ? signedPercent(scenarioResult.max_drawdown_pct, 1) : "—"} />
                        <ComparisonRow label="Diversification" current={currentAnalysis.data.diversification_score?.toFixed(2) ?? "—"} scenario={scenarioResult.diversification_score?.toFixed(2) ?? "—"} />
                      </tbody>
                    </table>
                  </div>
                </section>

                <section className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-md border border-line">
                    <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">Allocation: current vs. scenario</div>
                    <div className="flex flex-col gap-3 p-4">
                      {allDisplayedTickers.map((ticker) => {
                        const before = weightOf(currentAnalysis.data, ticker);
                        const after = weightOf(scenarioResult, ticker);
                        const changed = Math.abs(after - before) >= 0.5;
                        return (
                          <div key={ticker} className={`flex flex-col gap-1 rounded ${changed ? "bg-accent-soft/40 -mx-2 px-2 py-1" : ""}`}>
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-mono font-semibold text-ink">{ticker}</span>
                              <span className="font-mono text-ink-muted">{before.toFixed(1)}% → <span className={changed ? "font-bold text-ink" : ""}>{after.toFixed(1)}%</span></span>
                            </div>
                            <div className="relative h-2 overflow-hidden rounded-full bg-surface-alt">
                              <div className="absolute h-full rounded-full bg-line-strong" style={{ width: `${Math.min(before, 100)}%` }} />
                              <div className="absolute h-full rounded-full border-2 border-accent-strong" style={{ width: `${Math.min(after, 100)}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="rounded-md border border-line p-4">
                    <div className="mb-3 text-sm font-bold text-ink">Risk &amp; forecast impact</div>
                    {impactNotes.length === 0 ? (
                      <p className="text-sm text-ink-muted">No material change detected.</p>
                    ) : (
                      <ul className="flex flex-col gap-2 text-sm text-ink-muted">
                        {impactNotes.map((note, i) => (
                          <li key={i} className="flex gap-2"><span className="text-ink-faint">•</span><span>{note}</span></li>
                        ))}
                      </ul>
                    )}
                    <p className="mt-3 text-xs text-ink-faint">
                      Expected return is an LSTM model estimate, not a guarantee. Volatility/Sharpe/drawdown
                      use trailing 1-year historical data combined with each scenario's weights.
                    </p>
                  </div>
                </section>

                {mode === "rebalance" && (
                  <section>
                    <div className="mb-3 flex items-center gap-2 text-sm font-bold text-ink">
                      <StepBadge n={3} /> Review proposed changes
                    </div>
                    {proposedOrders.length === 0 ? (
                      <p className="text-sm text-ink-muted">This scenario doesn't require any trades — allocations already match.</p>
                    ) : !reviewing ? (
                      <Button onClick={() => setReviewing(true)}>Review Proposed Orders ({proposedOrders.length})</Button>
                    ) : (
                      <>
                        <div className="mb-3 flex items-center gap-2 text-sm font-bold text-ink">
                          <StepBadge n={4} /> Apply through existing trading confirmation
                        </div>
                        <ProposedOrdersReview orders={proposedOrders} onCancel={() => setReviewing(false)} />
                      </>
                    )}
                  </section>
                )}
                {mode === "shock" && (
                  <p className="text-xs text-ink-faint">
                    A price shock is a hypothetical market event, not an action you can execute — there are no
                    proposed orders for this scenario type.
                  </p>
                )}
              </>
            )}

            <details className="rounded-md border border-line p-4 text-sm">
              <summary className="cursor-pointer font-bold text-ink">Methodology &amp; limitations</summary>
              <ul className="mt-3 flex flex-col gap-2 text-xs text-ink-muted">
                <li>Scenario analysis evaluates a hypothetical portfolio — it never reads or writes your real positions, orders, or cash.</li>
                <li>Rebalance scenarios fund the weight change from/to cash; all untouched tickers keep their current dollar value.</li>
                <li>Price-shock scenarios keep share quantities fixed and change only the shocked ticker's price — every weight shifts as a side effect.</li>
                <li>Both "Current" and "Scenario" are computed through the identical risk/forecast pipeline, so the comparison is apples-to-apples.</li>
                <li>Risk metrics use trailing 1-year historical data; expected return is a per-ticker LSTM 22-day forecast, annualized — neither is a guarantee of future performance.</li>
                <li>Only Step 4's explicit confirmation places real orders, through the same trading endpoint as the Trading page.</li>
              </ul>
            </details>
          </>
        )}
      </QueryState>
    </div>
  );
}

function StepBadge({ n }: { n: number }) {
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ink-strong text-[11px] font-bold text-white">
      {n}
    </span>
  );
}

function ComparisonRow({ label, current, scenario }: { label: string; current: string; scenario: string }) {
  const changed = current !== scenario;
  return (
    <tr>
      <td className="px-4 py-2 font-sans text-ink-muted">{label}</td>
      <td className="px-4 py-2">{current}</td>
      <td className={`px-4 py-2 ${changed ? "font-bold text-ink" : "text-ink-muted"}`}>{scenario}</td>
    </tr>
  );
}
