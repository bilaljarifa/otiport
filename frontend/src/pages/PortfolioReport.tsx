import { useMemo } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  usePortfolioSummary, useQuotes, useEquityCurve, usePortfolioRisk,
  useForecastContext, useTickerNewsSummary, useOhlc,
} from "../lib/queries";
import { computeValuation } from "../lib/valuation";
import { money, percent, signedMoney, signedPercent } from "../lib/format";
import { QueryState } from "../components/QueryState";
import { Button } from "../components/Button";
import { EquityCurveChart } from "../components/analytics/EquityCurveChart";

/**
 * A single self-contained report assembled entirely from data already used
 * elsewhere in the app (portfolio summary, quotes, equity curve, risk
 * metrics, forecast-context, news) — nothing here is computed independently
 * or fabricated. "PDF" is the browser's own print-to-PDF via `window.print()`
 * plus print-only CSS (see index.css), rather than a new PDF dependency.
 */
export function PortfolioReportPage() {
  const { user } = useAuth();
  const summary = usePortfolioSummary();
  const tickers = useMemo(() => summary.data?.positions.map((p) => p.ticker) ?? [], [summary.data]);
  const quotes = useQuotes(tickers);
  const equityCurve = useEquityCurve();
  const risk = usePortfolioRisk();
  const benchmarkOhlc = useOhlc("SPY", "1y");

  const valuation = useMemo(() => {
    if (!summary.data) return null;
    if (tickers.length > 0 && !quotes.data) return null;
    return computeValuation(summary.data.positions, quotes.data?.quotes ?? {}, summary.data.account.cash, summary.data.account.initial_cash);
  }, [summary.data, quotes.data, tickers.length]);

  const topHolding = valuation?.holdings[0]?.ticker ?? "";
  const forecast = useForecastContext(topHolding, valuation?.holdings[0]?.price ?? undefined);
  const newsSummary = useTickerNewsSummary(topHolding);

  const benchmarkReturnPct = useMemo(() => {
    const bars = benchmarkOhlc.data?.bars;
    if (!bars || bars.length < 2) return null;
    return ((bars[bars.length - 1].close - bars[0].close) / bars[0].close) * 100;
  }, [benchmarkOhlc.data]);

  const isLoading = summary.isLoading || (tickers.length > 0 && quotes.isLoading);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <h1 className="text-xl font-bold text-ink">Portfolio Report</h1>
        <Button onClick={() => window.print()}>Print / Save as PDF</Button>
      </div>

      <QueryState isLoading={isLoading} isError={summary.isError} error={summary.error} onRetry={() => void summary.refetch()}>
        {valuation && summary.data && user && (
          <div className="flex flex-col gap-6 rounded-md border border-line p-6 print:border-0 print:p-0">
            <header className="border-b border-line pb-4">
              <h2 className="text-2xl font-bold text-ink">Optiport Portfolio Report</h2>
              <p className="mt-1 text-sm text-ink-muted">
                Simulated paper-trading account · Report generated {new Date().toLocaleString()}
              </p>
              <p className="mt-2 text-xs text-ink-faint">
                Data sources: Yahoo Finance (market data), NewsAPI + sentiment pipeline (news context), LSTM
                forecaster (return forecasts). This is a simulated account — no real money or brokerage is
                involved. Historical performance and forecasts are not guarantees of future results.
              </p>
            </header>

            <section>
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">Account Overview</h3>
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div><dt className="text-xs text-ink-faint">Name</dt><dd className="font-semibold text-ink">{user.full_name}</dd></div>
                <div><dt className="text-xs text-ink-faint">Username</dt><dd className="font-semibold text-ink">@{user.username}</dd></div>
                <div><dt className="text-xs text-ink-faint">Role</dt><dd className="font-semibold text-ink capitalize">{user.role}</dd></div>
                <div><dt className="text-xs text-ink-faint">Account since</dt><dd className="font-semibold text-ink">{new Date(user.created_at).toLocaleDateString()}</dd></div>
              </dl>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">Portfolio Summary</h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <ReportStat label="Portfolio Value" value={money(valuation.equity)} />
                <ReportStat label="Cash" value={money(valuation.cash)} />
                <ReportStat label="Invested" value={money(valuation.marketValue)} />
                <ReportStat label="Total Return" value={signedMoney(valuation.totalReturn)} sub={signedPercent(valuation.totalReturnPct)} />
                <ReportStat label="Today's P&L" value={signedMoney(valuation.dayPnl)} sub={signedPercent(valuation.dayPnlPct)} />
              </div>
            </section>

            {valuation.holdings.length > 0 && (
              <section>
                <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">Holdings &amp; Allocation</h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="py-1.5">Ticker</th><th className="py-1.5">Qty</th><th className="py-1.5">Price</th>
                      <th className="py-1.5">Market Value</th><th className="py-1.5">P&L</th><th className="py-1.5">Weight</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line-soft font-mono">
                    {valuation.holdings.map((h) => (
                      <tr key={h.ticker}>
                        <td className="py-1.5 font-sans font-semibold">{h.ticker}</td>
                        <td className="py-1.5">{h.quantity.toLocaleString()}</td>
                        <td className="py-1.5">{h.price != null ? money(h.price, 2) : "—"}</td>
                        <td className="py-1.5">{h.marketValue != null ? money(h.marketValue) : "—"}</td>
                        <td className={`py-1.5 ${h.pnl != null && h.pnl < 0 ? "text-down" : "text-up"}`}>{h.pnl != null ? signedMoney(h.pnl) : "—"}</td>
                        <td className="py-1.5">{h.weight != null ? percent(h.weight, 1) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}

            <section className="break-inside-avoid">
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">Performance</h3>
              {equityCurve.data && equityCurve.data.equity.length >= 2 ? (
                <>
                  <EquityCurveChart
                    points={equityCurve.data.dates.map((d, i) => ({ date: d, strategy_equity: equityCurve.data!.equity[i], benchmark_equity: null }))}
                    height={220}
                  />
                  <p className="mt-2 text-xs text-ink-faint">Reconstructed from the account's real transaction history.</p>
                </>
              ) : (
                <p className="text-sm text-ink-muted">Not enough account history yet to chart performance.</p>
              )}
            </section>

            <section className="break-inside-avoid">
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">Risk Metrics</h3>
              {risk.data?.status === "ok" ? (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  <ReportStat label="Volatility (ann.)" value={percent(risk.data.volatility_pct ?? 0, 1)} />
                  <ReportStat label="Sharpe Ratio" value={(risk.data.sharpe_ratio ?? 0).toFixed(2)} />
                  <ReportStat label="Max Drawdown" value={signedPercent(risk.data.max_drawdown_pct ?? 0, 1)} />
                  <ReportStat label={`Beta (vs ${risk.data.benchmark_ticker})`} value={risk.data.beta != null ? risk.data.beta.toFixed(2) : "—"} />
                  <ReportStat label="Diversification" value={risk.data.diversification_score != null ? risk.data.diversification_score.toFixed(2) : "—"} />
                </div>
              ) : (
                <p className="text-sm text-ink-muted">No open positions to analyze.</p>
              )}
              <p className="mt-2 text-xs text-ink-faint">
                Computed from the portfolio's current holdings combined with trailing 1-year historical
                returns — see the Risk Center for full methodology and limitations.
              </p>
            </section>

            <section className="break-inside-avoid">
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">Benchmark Comparison</h3>
              <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                <div><div className="text-xs text-ink-faint">Portfolio total return</div><div className="font-mono font-semibold text-ink">{signedPercent(valuation.totalReturnPct, 1)}</div></div>
                <div><div className="text-xs text-ink-faint">SPY, trailing 1 year</div><div className="font-mono font-semibold text-ink">{benchmarkReturnPct != null ? signedPercent(benchmarkReturnPct, 1) : "—"}</div></div>
              </div>
              <p className="mt-2 text-xs text-ink-faint">
                Portfolio return is since account inception; the SPY figure is a trailing 1-year window —
                the two periods may not align exactly.
              </p>
            </section>

            {topHolding && (
              <section className="break-inside-avoid">
                <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">
                  Forecast &amp; News Context — {topHolding} (largest holding)
                </h3>
                {forecast.data ? (
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div><div className="text-xs text-ink-faint">Base Forecast (model output)</div>
                      <div className="font-mono font-semibold text-ink">
                        {forecast.data.base_forecast.predicted_return_22d != null ? signedPercent(forecast.data.base_forecast.predicted_return_22d * 100) : "—"}
                      </div></div>
                    <div><div className="text-xs text-ink-faint">News-Context Adjustment</div>
                      <div className="font-mono font-semibold text-ink">{signedPercent(forecast.data.news_context_forecast.adjustment_22d * 100)}</div></div>
                    <div><div className="text-xs text-ink-faint">Context Forecast</div>
                      <div className="font-mono font-semibold text-ink">{signedPercent(forecast.data.news_context_forecast.predicted_return_22d * 100)}</div></div>
                  </div>
                ) : (
                  <p className="text-sm text-ink-muted">Forecast unavailable.</p>
                )}
                {newsSummary.data && (
                  <p className="mt-2 text-xs text-ink-muted">
                    News sentiment: {newsSummary.data.overall_sentiment} ({newsSummary.data.news_count} articles) ·
                    Market impact: {newsSummary.data.overall_market_impact}
                  </p>
                )}
                <p className="mt-2 text-xs text-ink-faint">{forecast.data?.disclaimer ?? ""}</p>
              </section>
            )}

            <section className="break-inside-avoid">
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-faint">Recent Transactions</h3>
              {summary.data.transactions.length === 0 ? (
                <p className="text-sm text-ink-muted">No transactions yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="py-1.5">Date</th><th className="py-1.5">Type</th><th className="py-1.5">Ticker</th><th className="py-1.5">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line-soft font-mono">
                    {summary.data.transactions.slice(0, 10).map((tx) => (
                      <tr key={tx.id}>
                        <td className="py-1.5">{new Date(tx.created_at).toLocaleDateString()}</td>
                        <td className="py-1.5 font-sans">{tx.type}</td>
                        <td className="py-1.5">{tx.ticker ?? "—"}</td>
                        <td className={`py-1.5 ${tx.amount >= 0 ? "text-up" : "text-down"}`}>{signedMoney(tx.amount, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <footer className="border-t border-line pt-4 text-xs text-ink-faint">
              Methodology &amp; limitations: forecasts come from per-ticker LSTM models trained on historical
              technical features and are not guarantees of future returns; news sentiment/impact are
              probabilistic estimates; risk metrics use the portfolio's current holdings combined with
              trailing historical data, not a replay of this account's actual trade-by-trade history. This
              report reflects a simulated paper-trading account only.
            </footer>
          </div>
        )}
      </QueryState>
    </div>
  );
}

function ReportStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="font-mono text-lg font-bold text-ink">{value}</div>
      {sub && <div className="text-xs text-ink-muted">{sub}</div>}
    </div>
  );
}
