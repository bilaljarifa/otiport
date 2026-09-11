import { useMemo } from "react";
import { Link } from "react-router-dom";
import { usePortfolioSummary, useQuotes } from "../lib/queries";
import { computeValuation } from "../lib/valuation";
import { money, signedMoney, signedPercent, percent } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";

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
                          <td className="px-4 py-2.5 font-sans font-semibold text-ink">{h.ticker}</td>
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
          </>
        )}
      </QueryState>
    </div>
  );
}
