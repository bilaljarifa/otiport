import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { usePortfolioSummary, useQuotes, useEquityCurve } from "../lib/queries";
import { computeValuation } from "../lib/valuation";
import { money, signedMoney, signedPercent, percent } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";
import { FilterGroup } from "../components/FilterGroup";
import { buttonClass } from "../components/buttonStyles";
import { EquityCurveChart } from "../components/analytics/EquityCurveChart";

const MARKET_OVERVIEW = ["SPY", "QQQ", "PSI", "IYW", "NLR", "UTES"];

type Range = "1W" | "1M" | "3M" | "6M" | "1Y" | "ALL";
const RANGE_DAYS: Record<Exclude<Range, "ALL">, number> = {
  "1W": 7, "1M": 30, "3M": 91, "6M": 182, "1Y": 365,
};
const RANGES: { value: Range; label: string }[] = [
  { value: "1W", label: "1W" },
  { value: "1M", label: "1M" },
  { value: "3M", label: "3M" },
  { value: "6M", label: "6M" },
  { value: "1Y", label: "1Y" },
  { value: "ALL", label: "ALL" },
];
const DEFAULT_RANGE_ORDER: Exclude<Range, "ALL">[] = ["1Y", "6M", "3M", "1M", "1W"];

/** Below this, a chart's real span is real but not yet informative enough
 * to draw range-over-range conclusions from — still shown (never hidden),
 * just flagged so a 3-day line isn't mistaken for a settled trend. */
const MEANINGFUL_HISTORY_DAYS = 30;

/** The largest bucket the account's real history can actually fill —
 * never defaults to a window that would render as a near-empty sliver. */
function pickDefaultRange(spanDays: number): Range {
  for (const r of DEFAULT_RANGE_ORDER) {
    if (spanDays >= RANGE_DAYS[r]) return r;
  }
  return "ALL";
}

const PRIMARY_ACTION = { to: "/app/trading", label: "Trade" };
const SECONDARY_ACTIONS = [
  { to: "/app/analytics", label: "Analytics" },
  { to: "/app/watchlist", label: "Watchlist" },
  { to: "/app/assistant", label: "AI Assistant" },
];

export function DashboardPage() {
  const summary = usePortfolioSummary();
  const equityCurve = useEquityCurve();
  const [manualRange, setManualRange] = useState<Range | null>(null);

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

  const totalPoints = equityCurve.data?.dates.length ?? 0;
  const hasEquityHistory = totalPoints >= 2;

  const spanDays = useMemo(() => {
    const dates = equityCurve.data?.dates ?? [];
    if (dates.length < 2) return 0;
    const first = new Date(dates[0]).getTime();
    const last = new Date(dates[dates.length - 1]).getTime();
    return Math.round((last - first) / 86_400_000);
  }, [equityCurve.data]);

  const isLimitedHistory = hasEquityHistory && spanDays < MEANINGFUL_HISTORY_DAYS;

  // Whether the account's *entire* real equity history actually moved by
  // enough to be worth plotting as a chart — a flat $250,000 line (never
  // traded, or traded today with prices essentially unchanged) has the same
  // near-zero information content whether it spans 1 day or 25; stretching
  // it across a full-size chart communicates nothing. 0.5% of the account's
  // own initial deposit is a small, disclosed, non-arbitrary-feeling bar —
  // real day-to-day cash/market noise, not a claim about what's "big".
  const equityValues = equityCurve.data?.equity ?? [];
  const equitySwing = equityValues.length > 0 ? Math.max(...equityValues) - Math.min(...equityValues) : 0;
  const initialCash = summary.data?.account.initial_cash ?? 0;
  const hasMeaningfulMovement = initialCash > 0 && equitySwing / initialCash >= 0.005;
  const showCompactHistory = hasEquityHistory && !hasMeaningfulMovement;

  const effectiveRange = manualRange ?? pickDefaultRange(spanDays);

  const rangeOptions = useMemo(
    () =>
      RANGES.map((r) => {
        if (r.value === "ALL") return { ...r, disabled: false, title: undefined };
        const needed = RANGE_DAYS[r.value];
        const disabled = spanDays < needed;
        return {
          ...r,
          disabled,
          title: disabled ? `Not enough history yet — need ${needed}+ days, ${spanDays} available` : undefined,
        };
      }),
    [spanDays],
  );

  const now = Date.now();
  const chartPoints = useMemo(() => {
    const dates = equityCurve.data?.dates ?? [];
    const equity = equityCurve.data?.equity ?? [];
    let sliceFrom = 0;
    if (effectiveRange !== "ALL") {
      const cutoff = now - RANGE_DAYS[effectiveRange] * 86_400_000;
      sliceFrom = dates.findIndex((d) => new Date(d).getTime() >= cutoff);
      if (sliceFrom === -1) sliceFrom = 0;
    }
    return dates
      .slice(sliceFrom)
      .map((date, i) => ({ date, strategy_equity: equity[sliceFrom + i], benchmark_equity: null }));
  }, [equityCurve.data, effectiveRange, now]);

  const selectedSpanDays =
    chartPoints.length >= 2
      ? Math.round(
          (new Date(chartPoints[chartPoints.length - 1].date).getTime() -
            new Date(chartPoints[0].date).getTime()) /
            86_400_000,
        )
      : 0;
  const periodChangeAbs =
    chartPoints.length >= 2
      ? chartPoints[chartPoints.length - 1].strategy_equity - chartPoints[0].strategy_equity
      : null;
  const firstPointEquity = chartPoints[0]?.strategy_equity ?? 0;
  const periodChangePct =
    periodChangeAbs !== null && firstPointEquity ? (periodChangeAbs / firstPointEquity) * 100 : null;
  const showPeriodPct = selectedSpanDays >= 7;

  const hasPositions = (valuation?.holdings.length ?? 0) > 0;

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
            {/* Portfolio overview */}
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <StatTile label="Total Equity" value={money(valuation.equity)} />
              <StatTile label="Available Cash" value={money(valuation.cash)} />
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

            {/* Dashboard actions — one primary action, the rest secondary */}
            <div className="flex flex-wrap items-center gap-2">
              <Link to={PRIMARY_ACTION.to} className={buttonClass("accent")}>
                {PRIMARY_ACTION.label} →
              </Link>
              {SECONDARY_ACTIONS.map((a) => (
                <Link key={a.to} to={a.to} className={buttonClass("secondary")}>
                  {a.label}
                </Link>
              ))}
            </div>

            {!hasPositions && (
              <div className="rounded-md border border-dashed border-line-strong px-6 py-10 text-center">
                <p className="text-base font-bold text-ink">Your portfolio is ready.</p>
                <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">
                  Use the paper-trading terminal to build your first position — every price and fill
                  uses real, live market data. You're starting with {money(valuation.cash)} in
                  simulated cash.
                </p>
                <div className="mt-4 flex justify-center">
                  <Link to="/app/trading" className={buttonClass("accent")}>
                    Trade ETFs →
                  </Link>
                </div>
              </div>
            )}

            {/* Account & buying power */}
            <section className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Account &amp; Buying Power
              </div>
              <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-5">
                <StatTile label="Total Equity" value={money(valuation.equity)} />
                <StatTile label="Available Cash" value={money(valuation.cash)} />
                <StatTile label="Invested" value={money(valuation.marketValue)} />
                <StatTile
                  label="Buying Power"
                  value={money(valuation.cash)}
                  hint="Cash-settled · no margin"
                />
                <StatTile label="Open Positions" value={String(summary.data.positions.length)} />
              </div>
            </section>

            {/* Performance */}
            <section className="rounded-md border border-line">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
                <div>
                  <span className="text-sm font-bold text-ink">Performance</span>
                  {hasEquityHistory && (
                    <p className="mt-0.5 text-xs text-ink-faint">
                      {spanDays} day{spanDays === 1 ? "" : "s"} of portfolio history available
                    </p>
                  )}
                </div>
                {hasEquityHistory && !showCompactHistory && (
                  <FilterGroup value={effectiveRange} onChange={setManualRange} options={rangeOptions} />
                )}
              </div>

              <QueryState
                isLoading={equityCurve.isLoading}
                isError={equityCurve.isError}
                error={equityCurve.error}
                onRetry={() => void equityCurve.refetch()}
              >
                {!hasEquityHistory ? (
                  <div className="flex flex-col items-center gap-4 px-6 py-10 text-center">
                    {!hasPositions && (
                      <p className="text-base font-bold text-ink">Your portfolio is ready to trade.</p>
                    )}
                    <div className="grid w-full max-w-lg grid-cols-2 gap-3 sm:grid-cols-4">
                      <StatTile label="Available Capital" value={money(valuation.cash)} />
                      <StatTile label="Invested" value={money(valuation.marketValue)} />
                      <StatTile label="Open Positions" value={String(summary.data.positions.length)} />
                      <StatTile
                        label="P&L"
                        value={signedMoney(valuation.totalReturn)}
                        delta={{ value: signedPercent(valuation.totalReturnPct), positive: valuation.totalReturn >= 0 }}
                      />
                    </div>
                    {hasPositions ? (
                      <p className="max-w-sm text-sm text-ink-muted">
                        Your account only has one day of history so far — the performance chart will
                        populate as more trading days pass.
                      </p>
                    ) : (
                      <>
                        <p className="max-w-sm text-sm text-ink-muted">
                          Performance analytics will become available as your portfolio builds trading
                          history.
                        </p>
                        <Link to="/app/trading" className={buttonClass("accent")}>
                          Start Trading →
                        </Link>
                      </>
                    )}
                  </div>
                ) : showCompactHistory ? (
                  <div className="flex flex-col items-center gap-4 px-6 py-8 text-center">
                    <div className="grid w-full max-w-2xl grid-cols-2 gap-3 sm:grid-cols-5">
                      <StatTile label="Current Value" value={money(valuation.equity)} />
                      <StatTile label="Available Cash" value={money(valuation.cash)} />
                      <StatTile label="Invested" value={money(valuation.marketValue)} />
                      <StatTile label="Open Positions" value={String(summary.data.positions.length)} />
                      <StatTile
                        label="P&L"
                        value={signedMoney(valuation.totalReturn)}
                        delta={{ value: signedPercent(valuation.totalReturnPct), positive: valuation.totalReturn >= 0 }}
                      />
                    </div>
                    <div className="w-full max-w-md rounded-md border border-dashed border-line-strong px-4 py-4">
                      <p className="text-sm font-bold text-ink">Limited portfolio history</p>
                      <p className="mt-1.5 text-sm text-ink-muted">
                        Your account currently has {spanDays} day{spanDays === 1 ? "" : "s"} of portfolio
                        history. Performance analytics will become more meaningful as you trade.
                      </p>
                      {!hasPositions && (
                        <div className="mt-3 flex justify-center">
                          <Link to="/app/trading" className={buttonClass("accent")}>
                            Start Trading →
                          </Link>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <>
                    {isLimitedHistory && (
                      <div className="border-b border-line-soft bg-surface-alt px-4 py-2.5 text-xs text-ink-muted">
                        <span className="font-semibold text-ink">Limited portfolio history</span> —{" "}
                        {spanDays} day{spanDays === 1 ? "" : "s"} of portfolio history available.
                        Performance will become more meaningful as you trade.
                      </div>
                    )}
                    <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-line-soft px-4 py-2.5 text-xs">
                      <span className="text-ink-muted">
                        Current value{" "}
                        <span className="font-mono font-semibold text-ink">{money(valuation.equity)}</span>
                      </span>
                      {periodChangeAbs !== null && (
                        <span className="text-ink-muted">
                          {effectiveRange} change{" "}
                          <span
                            className={`font-mono font-semibold ${periodChangeAbs >= 0 ? "text-up" : "text-down"}`}
                          >
                            {signedMoney(periodChangeAbs)}
                            {showPeriodPct && periodChangePct !== null && ` (${signedPercent(periodChangePct)})`}
                          </span>
                        </span>
                      )}
                    </div>
                    <div className="p-2">
                      <EquityCurveChart points={chartPoints} height={280} />
                    </div>
                    <p className="border-t border-line-soft px-4 py-2 text-xs text-ink-faint">
                      Reconstructed from your account's real transaction history — daily granularity,
                      not intraday.
                    </p>
                  </>
                )}
              </QueryState>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-md border border-line">
                <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                  Market overview
                </div>
                <div className="divide-y divide-line-soft">
                  {MARKET_OVERVIEW.map((ticker) => {
                    const quote = quotes.data?.quotes[ticker];
                    return (
                      <Link
                        key={ticker}
                        to={`/app/research/${ticker}`}
                        className="flex items-center justify-between px-4 py-2 hover:bg-surface-alt"
                      >
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
                      </Link>
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
                        <Link
                          key={ticker}
                          to={`/app/research/${ticker}`}
                          className="flex items-center justify-between px-4 py-2 hover:bg-surface-alt"
                        >
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
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>

            {hasPositions && (
              <section className="rounded-md border border-line p-4">
                <div className="mb-3 text-sm font-bold text-ink">Allocation by ETF</div>
                <div className="flex flex-col gap-2">
                  {valuation.holdings.map((h) => (
                    <div key={h.ticker} className="flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono font-semibold text-ink">{h.ticker}</span>
                        <span className="text-ink-muted">
                          {h.weight !== null ? percent(h.weight, 1) : "—"} ·{" "}
                          {h.marketValue !== null ? money(h.marketValue) : "—"}
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
                        <div
                          className="h-full rounded-full bg-accent-strong"
                          style={{ width: `${Math.min(h.weight ?? 0, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Holdings
              </div>
              {valuation.holdings.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-ink-muted">
                  No open positions. <Link to="/app/trading" className="font-semibold underline">Place a trade →</Link>
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-sm">
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
                          <td className="px-4 py-2 font-sans font-semibold">
                            <Link to={`/app/research/${h.ticker}`} className="hover:underline">
                              {h.ticker}
                            </Link>
                          </td>
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
                </div>
              )}
            </section>

            <section className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Recent activity
              </div>
              {summary.data.transactions.length === 0 && summary.data.orders.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-ink-muted">No activity yet.</p>
              ) : (
                <div className="divide-y divide-line-soft">
                  {summary.data.transactions.slice(0, 6).map((tx) => (
                    <div key={`tx-${tx.id}`} className="flex items-center justify-between px-4 py-2 text-sm">
                      <div>
                        <span className="font-semibold">{tx.type}</span>
                        {tx.ticker && <span className="ml-2 font-mono text-ink-muted">{tx.ticker}</span>}
                        <span className="ml-2 text-xs text-ink-faint">
                          {new Date(tx.created_at).toLocaleDateString()}
                        </span>
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
