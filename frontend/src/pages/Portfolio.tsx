import { useMemo } from "react";
import { Link } from "react-router-dom";
import { usePortfolioSummary, useQuotes, useAttribution } from "../lib/queries";
import { computeValuation } from "../lib/valuation";
import { money, signedMoney, signedPercent, percent } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";
import type { HoldingContribution } from "../lib/portfolioApi";

function ContributionRow({ holding }: { holding: HoldingContribution }) {
  const isPositive = holding.contribution >= 0;
  return (
    <div className="flex flex-col gap-1 px-4 py-2.5">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2">
          <span className="font-mono font-semibold text-ink">{holding.ticker}</span>
          {!holding.is_open_position && (
            <span className="rounded bg-surface-alt px-1.5 py-0.5 text-[10px] font-semibold uppercase text-ink-faint">
              Closed
            </span>
          )}
        </span>
        <span className={`font-mono font-semibold ${isPositive ? "text-up" : "text-down"}`}>
          {signedMoney(holding.contribution)}
          {holding.contribution_pct != null && (
            <span className="ml-1.5 text-xs text-ink-faint">({signedPercent(holding.contribution_pct, 1)})</span>
          )}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
        <div
          className={`h-full rounded-full ${isPositive ? "bg-up" : "bg-down"}`}
          style={{ width: `${Math.min(Math.abs(holding.contribution_pct ?? 0), 100)}%` }}
        />
      </div>
    </div>
  );
}

function PerformanceAttributionSection() {
  const attribution = useAttribution();
  const data = attribution.data;

  return (
    <section className="rounded-md border border-line">
      <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
        Performance Attribution
      </div>

      <QueryState
        isLoading={attribution.isLoading}
        isError={attribution.isError}
        error={attribution.error}
        onRetry={() => void attribution.refetch()}
      >
        {data?.status === "insufficient_history" ? (
          <div className="px-4 py-8 text-center">
            <p className="text-sm font-bold text-ink">Insufficient portfolio history</p>
            <p className="mx-auto mt-1.5 max-w-sm text-sm text-ink-muted">
              Performance attribution requires sufficient transaction and valuation history.{" "}
              {data.detail}
            </p>
          </div>
        ) : data?.status === "ok" ? (
          <>
            <div className="flex items-center justify-between border-b border-line-soft px-4 py-2.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                Total Portfolio Return (since inception)
              </span>
              <span className={`font-mono text-lg font-bold ${data.total_return! >= 0 ? "text-up" : "text-down"}`}>
                {signedMoney(data.total_return!)}
              </span>
            </div>

            <div className="border-b border-line-soft px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Contribution by holding
            </div>
            <div className="divide-y divide-line-soft">
              {data.holdings.map((h) => (
                <ContributionRow key={h.ticker} holding={h} />
              ))}
            </div>

            <div className="grid gap-4 border-t border-line-soft p-4 sm:grid-cols-2">
              <div className="rounded-md border border-line-soft p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                  Largest Contributor
                </div>
                {data.largest_contributor ? (
                  <div className="mt-1.5 flex items-baseline justify-between">
                    <span className="font-mono font-semibold text-ink">{data.largest_contributor.ticker}</span>
                    <span className="font-mono font-semibold text-up">
                      {signedMoney(data.largest_contributor.contribution)}
                    </span>
                  </div>
                ) : (
                  <p className="mt-1.5 text-sm text-ink-faint">None — no holding contributed positively.</p>
                )}
              </div>
              <div className="rounded-md border border-line-soft p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                  Largest Detractor
                </div>
                {data.largest_detractor ? (
                  <div className="mt-1.5 flex items-baseline justify-between">
                    <span className="font-mono font-semibold text-ink">{data.largest_detractor.ticker}</span>
                    <span className="font-mono font-semibold text-down">
                      {signedMoney(data.largest_detractor.contribution)}
                    </span>
                  </div>
                ) : (
                  <p className="mt-1.5 text-sm text-ink-faint">None — no holding detracted.</p>
                )}
              </div>
            </div>

            {data.region_contributions.length > 1 && (
              <div className="border-t border-line-soft p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                  Region contribution
                </div>
                <div className="flex flex-col gap-2">
                  {data.region_contributions.map((r) => (
                    <div key={r.region} className="flex items-center justify-between text-sm">
                      <span className="text-ink-muted">{r.region}</span>
                      <span className={`font-mono font-semibold ${r.contribution >= 0 ? "text-up" : "text-down"}`}>
                        {signedMoney(r.contribution)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {data.methodology && (
              <details className="border-t border-line-soft p-4 text-sm">
                <summary className="cursor-pointer font-bold text-ink">Methodology &amp; limitations</summary>
                <ul className="mt-3 flex flex-col gap-2 text-xs text-ink-muted">
                  <li className="flex gap-2">
                    <span className="text-ink-faint">•</span>
                    <span>{data.methodology.description}</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-ink-faint">•</span>
                    <span>Period: {data.methodology.period}</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-ink-faint">•</span>
                    <span>
                      Contribution % is only shown when the total return is at least{" "}
                      {money(data.methodology.contribution_pct_minimum_total_return)} in magnitude —
                      below that, a percentage would be technically defined but not meaningfully
                      interpretable.
                    </span>
                  </li>
                </ul>
              </details>
            )}
          </>
        ) : null}
      </QueryState>
    </section>
  );
}

export function PortfolioPage() {
  const summary = usePortfolioSummary();
  const tickers = useMemo(() => summary.data?.positions.map((p) => p.ticker) ?? [], [summary.data]);
  const quotes = useQuotes(tickers);

  // useQuotes([]) is intentionally disabled (nothing to look up) and never
  // resolves — with zero positions it must not block rendering forever.
  const hasPositions = tickers.length > 0;
  const isLoading = summary.isLoading || (hasPositions && quotes.isLoading);
  const isError = summary.isError || (hasPositions && quotes.isError);

  const valuation = useMemo(() => {
    if (!summary.data) return null;
    if (hasPositions && !quotes.data) return null;
    return computeValuation(
      summary.data.positions,
      quotes.data?.quotes ?? {},
      summary.data.account.cash,
      summary.data.account.initial_cash,
    );
  }, [summary.data, quotes.data, hasPositions]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Portfolio</h1>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={summary.error ?? quotes.error}
        onRetry={() => {
          void summary.refetch();
          void quotes.refetch();
        }}
      >
        {valuation && summary.data && (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <StatTile label="Portfolio Value" value={money(valuation.equity)} />
              <StatTile label="Cash" value={money(valuation.cash)} />
              <StatTile
                label="Invested"
                value={money(valuation.marketValue)}
                hint={percent(valuation.investedPct, 0)}
              />
              <StatTile
                label="Today's P&L"
                value={signedMoney(valuation.dayPnl)}
                delta={{ value: signedPercent(valuation.dayPnlPct), positive: valuation.dayPnl >= 0 }}
              />
              <StatTile
                label="Total Return"
                value={signedMoney(valuation.totalReturn)}
                delta={{ value: signedPercent(valuation.totalReturnPct), positive: valuation.totalReturn >= 0 }}
              />
            </div>

            <section className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Holdings
              </div>
              {valuation.holdings.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-ink-muted">
                  No open positions.{" "}
                  <Link to="/app/trading" className="font-semibold underline underline-offset-2">
                    Place a trade →
                  </Link>
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                        <th className="px-4 py-2 font-semibold">Ticker</th>
                        <th className="px-4 py-2 font-semibold">Quantity</th>
                        <th className="px-4 py-2 font-semibold">Avg Cost</th>
                        <th className="px-4 py-2 font-semibold">Current Price</th>
                        <th className="px-4 py-2 font-semibold">Market Value</th>
                        <th className="px-4 py-2 font-semibold">Unrealized P&L</th>
                        <th className="px-4 py-2 font-semibold">Today</th>
                        <th className="px-4 py-2 font-semibold">Allocation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line-soft font-mono">
                      {valuation.holdings.map((h) => (
                        <tr key={h.ticker}>
                          <td className="px-4 py-2.5 font-sans font-semibold text-ink">
                            <Link
                              to={`/app/research/${encodeURIComponent(h.ticker)}`}
                              className="hover:underline"
                            >
                              {h.ticker}
                            </Link>
                          </td>
                          <td className="px-4 py-2.5">{h.quantity.toLocaleString()}</td>
                          <td className="px-4 py-2.5">{money(h.avgPrice, 2)}</td>
                          <td className="px-4 py-2.5">{h.price !== null ? money(h.price, 2) : "—"}</td>
                          <td className="px-4 py-2.5">
                            {h.marketValue !== null ? money(h.marketValue) : "—"}
                          </td>
                          <td className={`px-4 py-2.5 ${h.pnl !== null && h.pnl < 0 ? "text-down" : "text-up"}`}>
                            {h.pnl !== null ? (
                              <>
                                {signedMoney(h.pnl)}{" "}
                                <span className="text-xs">
                                  ({h.pnlPct !== null ? signedPercent(h.pnlPct) : "—"})
                                </span>
                              </>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td
                            className={`px-4 py-2.5 ${h.dayPnl !== null && h.dayPnl < 0 ? "text-down" : "text-up"}`}
                          >
                            {h.dayPnl !== null ? signedMoney(h.dayPnl) : "—"}
                          </td>
                          <td className="px-4 py-2.5">{h.weight !== null ? percent(h.weight) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <PerformanceAttributionSection />
          </>
        )}
      </QueryState>
    </div>
  );
}
