import { useMemo } from "react";
import { Link } from "react-router-dom";
import { usePortfolioSummary, useQuotes } from "../lib/queries";
import { computeValuation } from "../lib/valuation";
import { money, signedMoney, signedPercent, percent } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";

const MARKET_OVERVIEW = ["SPY", "QQQ", "PSI", "IYW", "NLR", "UTES"];

export function DashboardPage() {
  const summary = usePortfolioSummary();

  // Deliberately `[]` (not just the static MARKET_OVERVIEW list) until
  // `summary.data` resolves: computing it from `summary.data ?? { positions:
  // [], watchlist: [] }` would fire useQuotes immediately with an incomplete
  // ticker set, then again moments later once real positions/watchlist
  // tickers are known — two round trips (one wasted) instead of one.
  const allTickers = useMemo(() => {
    if (!summary.data) return [];
    const positionTickers = summary.data.positions.map((p) => p.ticker);
    return Array.from(new Set([...MARKET_OVERVIEW, ...positionTickers, ...summary.data.watchlist]));
  }, [summary.data]);
  const quotes = useQuotes(allTickers);
  const watchlistTickers = summary.data?.watchlist ?? [];

  const isLoading = summary.isLoading || quotes.isLoading;
  const isError = summary.isError || quotes.isError;

  const valuation = useMemo(() => {
    if (!summary.data || !quotes.data) return null;
    return computeValuation(
      summary.data.positions,
      quotes.data.quotes,
      summary.data.account.cash,
      summary.data.account.initial_cash,
    );
  }, [summary.data, quotes.data]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Dashboard</h1>

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
              <StatTile label="Invested" value={money(valuation.marketValue)} hint={percent(valuation.investedPct, 0)} />
              <StatTile
                label="Today's P&L"
                value={signedMoney(valuation.dayPnl)}
                delta={{ value: signedPercent(valuation.dayPnlPct), positive: valuation.dayPnl >= 0 }}
              />
              <StatTile
                label="Total P&L"
                value={signedMoney(valuation.totalReturn)}
                delta={{ value: signedPercent(valuation.totalReturnPct), positive: valuation.totalReturn >= 0 }}
              />
            </div>

            <section className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-md border border-line">
                <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                  Market overview
                </div>
                <div className="divide-y divide-line-soft">
                  {MARKET_OVERVIEW.map((ticker) => {
                    const quote = quotes.data?.quotes[ticker];
                    return (
                      <div key={ticker} className="flex items-center justify-between px-4 py-2">
                        <span className="font-mono text-sm font-semibold">{ticker}</span>
                        {quote ? (
                          <span className="flex items-center gap-3 font-mono text-sm">
                            <span>{money(quote.price, 2)}</span>
                            <span className={quote.change_pct >= 0 ? "text-up" : "text-down"}>
                              {signedPercent(quote.change_pct)}
                            </span>
                          </span>
                        ) : (
                          <span className="text-xs text-ink-faint">unavailable</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-md border border-line">
                <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                  <span className="text-sm font-bold text-ink">Watchlist</span>
                  <Link to="/app/watchlist" className="text-xs font-semibold text-ink-muted hover:text-ink">
                    Manage →
                  </Link>
                </div>
                {watchlistTickers.length === 0 ? (
                  <p className="px-4 py-6 text-center text-sm text-ink-muted">
                    No instruments on your watchlist yet.
                  </p>
                ) : (
                  <div className="divide-y divide-line-soft">
                    {watchlistTickers.map((ticker) => {
                      const quote = quotes.data?.quotes[ticker];
                      return (
                        <div key={ticker} className="flex items-center justify-between px-4 py-2">
                          <span className="font-mono text-sm font-semibold">{ticker}</span>
                          {quote ? (
                            <span className="flex items-center gap-3 font-mono text-sm">
                              <span>{money(quote.price, 2)}</span>
                              <span className={quote.change_pct >= 0 ? "text-up" : "text-down"}>
                                {signedPercent(quote.change_pct)}
                              </span>
                            </span>
                          ) : (
                            <span className="text-xs text-ink-faint">unavailable</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Holdings
              </div>
              {valuation.holdings.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-ink-muted">
                  No open positions. <Link to="/app/trading" className="font-semibold underline">Place a trade →</Link>
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="px-4 py-2 font-semibold">Ticker</th>
                      <th className="px-4 py-2 font-semibold">Qty</th>
                      <th className="px-4 py-2 font-semibold">Avg Cost</th>
                      <th className="px-4 py-2 font-semibold">Price</th>
                      <th className="px-4 py-2 font-semibold">Market Value</th>
                      <th className="px-4 py-2 font-semibold">P&L</th>
                      <th className="px-4 py-2 font-semibold">Weight</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line-soft font-mono">
                    {valuation.holdings.map((h) => (
                      <tr key={h.ticker}>
                        <td className="px-4 py-2 font-sans font-semibold">{h.ticker}</td>
                        <td className="px-4 py-2">{h.quantity.toLocaleString()}</td>
                        <td className="px-4 py-2">{money(h.avgPrice, 2)}</td>
                        <td className="px-4 py-2">{h.price !== null ? money(h.price, 2) : "—"}</td>
                        <td className="px-4 py-2">{h.marketValue !== null ? money(h.marketValue) : "—"}</td>
                        <td className={`px-4 py-2 ${h.pnl !== null && h.pnl < 0 ? "text-down" : "text-up"}`}>
                          {h.pnl !== null ? signedMoney(h.pnl) : "—"}
                        </td>
                        <td className="px-4 py-2">{h.weight !== null ? percent(h.weight) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Recent transactions
              </div>
              {summary.data.transactions.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-ink-muted">No transactions yet.</p>
              ) : (
                <div className="divide-y divide-line-soft">
                  {summary.data.transactions.slice(0, 6).map((tx) => (
                    <div key={tx.id} className="flex items-center justify-between px-4 py-2 text-sm">
                      <div>
                        <span className="font-semibold">{tx.type}</span>
                        {tx.ticker && <span className="ml-2 font-mono text-ink-muted">{tx.ticker}</span>}
                      </div>
                      <span className={`font-mono font-semibold ${tx.amount >= 0 ? "text-up" : "text-down"}`}>
                        {signedMoney(tx.amount, 2)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </QueryState>
    </div>
  );
}
