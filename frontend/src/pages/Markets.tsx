import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOhlc, useQuotes, useWatchlist, watchlistKey } from "../lib/queries";
import { addToWatchlist, removeFromWatchlist } from "../lib/portfolioApi";
import type { ChartPeriod } from "../lib/marketApi";
import { money, signedMoney, signedPercent } from "../lib/format";
import { CandlestickChart } from "../components/CandlestickChart";
import { QueryState } from "../components/QueryState";
import { buttonClass } from "../components/buttonStyles";
import { ETF_UNIVERSE, TICKER_PATTERN } from "../lib/catalog";

const PERIODS: { value: ChartPeriod; label: string }[] = [
  { value: "1mo", label: "1M" },
  { value: "3mo", label: "3M" },
  { value: "6mo", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "2y", label: "2Y" },
  { value: "5y", label: "5Y" },
];

export function MarketsPage() {
  const [ticker, setTicker] = useState("SPY");
  const [period, setPeriod] = useState<ChartPeriod>("6mo");
  const [searchInput, setSearchInput] = useState("");
  const [searchError, setSearchError] = useState<string | null>(null);

  const quote = useQuotes([ticker]);
  const ohlc = useOhlc(ticker, period);
  const watchlist = useWatchlist();
  const watchlistTickers = watchlist.data?.tickers ?? [];
  const watchlistQuotes = useQuotes(watchlistTickers);
  const queryClient = useQueryClient();

  const isWatched = watchlistTickers.includes(ticker);

  function invalidateWatchlist() {
    void queryClient.invalidateQueries({ queryKey: watchlistKey });
    void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
  }

  const addMutation = useMutation({ mutationFn: addToWatchlist, onSuccess: invalidateWatchlist });
  const removeMutation = useMutation({ mutationFn: removeFromWatchlist, onSuccess: invalidateWatchlist });

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    const candidate = searchInput.trim().toUpperCase();
    if (!TICKER_PATTERN.test(candidate)) {
      setSearchError("Enter a valid ticker symbol (1-6 letters).");
      return;
    }
    setSearchError(null);
    setTicker(candidate);
    setSearchInput("");
  }

  const q = quote.data?.quotes[ticker];
  const priceMissing = quote.data?.missing.includes(ticker);

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <div className="flex flex-1 flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search ticker (e.g. SPY)"
              className="w-48 rounded border border-line-strong bg-surface px-3 py-1.5 text-sm font-mono uppercase text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
            />
            <button type="submit" className={buttonClass("secondary", "px-3 py-1.5")}>
              Go
            </button>
          </form>
          {searchError && <span className="text-xs text-down">{searchError}</span>}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {ETF_UNIVERSE.map((etf) => (
            <button
              key={etf.ticker}
              onClick={() => setTicker(etf.ticker)}
              title={etf.name}
              className={`rounded px-2.5 py-1 text-xs font-mono font-semibold ${
                ticker === etf.ticker
                  ? "bg-accent-soft text-ink"
                  : "text-ink-muted hover:bg-surface-alt hover:text-ink"
              }`}
            >
              {etf.ticker}
            </button>
          ))}
        </div>

        <div className="rounded-md border border-line">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-lg font-bold text-ink">{ticker}</span>
              {quote.isLoading ? (
                <span className="text-xs text-ink-faint">Loading…</span>
              ) : q ? (
                <>
                  <span className="font-mono text-xl font-bold text-ink">{money(q.price, 2)}</span>
                  <span
                    className={`font-mono text-sm font-semibold ${q.change_pct >= 0 ? "text-up" : "text-down"}`}
                  >
                    {signedMoney(q.change_abs, 2)} ({signedPercent(q.change_pct)})
                  </span>
                </>
              ) : (
                <span className="text-xs text-ink-faint">
                  {priceMissing ? "Price unavailable" : ""}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  isWatched ? removeMutation.mutate(ticker) : addMutation.mutate(ticker)
                }
                disabled={addMutation.isPending || removeMutation.isPending}
                className={buttonClass(isWatched ? "secondary" : "primary", "px-3 py-1.5")}
              >
                {isWatched ? "− Remove from watchlist" : "+ Add to watchlist"}
              </button>
              <Link
                to={`/app/trading?ticker=${encodeURIComponent(ticker)}`}
                className={buttonClass("accent", "px-3 py-1.5")}
              >
                Trade
              </Link>
            </div>
          </div>

          <div className="flex items-center gap-1 border-b border-line px-4 py-2">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`rounded px-2.5 py-1 text-xs font-semibold ${
                  period === p.value
                    ? "bg-surface-alt text-ink"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <QueryState
            isLoading={ohlc.isLoading}
            isError={ohlc.isError}
            error={ohlc.error}
            onRetry={() => void ohlc.refetch()}
            isEmpty={ohlc.data !== undefined && ohlc.data.bars.length === 0}
            emptyMessage={`No chart data available for ${ticker}.`}
          >
            <div className="px-2 py-2">
              <CandlestickChart bars={ohlc.data?.bars ?? []} />
            </div>
          </QueryState>
        </div>
      </div>

      <div className="w-full shrink-0 lg:w-64">
        <div className="rounded-md border border-line">
          <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
            Watchlist
          </div>
          <QueryState
            isLoading={watchlist.isLoading}
            isError={watchlist.isError}
            error={watchlist.error}
            isEmpty={watchlistTickers.length === 0}
            emptyMessage="No instruments on your watchlist yet."
          >
            <div className="divide-y divide-line-soft">
              {watchlistTickers.map((t) => {
                const wq = watchlistQuotes.data?.quotes[t];
                return (
                  <button
                    key={t}
                    onClick={() => setTicker(t)}
                    className={`flex w-full items-center justify-between px-4 py-2 text-left ${
                      t === ticker ? "bg-accent-soft" : "hover:bg-surface-alt"
                    }`}
                  >
                    <span className="font-mono text-sm font-semibold text-ink">{t}</span>
                    {wq ? (
                      <span className="flex items-center gap-2 font-mono text-xs">
                        <span className="text-ink">{money(wq.price, 2)}</span>
                        <span className={wq.change_pct >= 0 ? "text-up" : "text-down"}>
                          {signedPercent(wq.change_pct)}
                        </span>
                      </span>
                    ) : (
                      <span className="text-xs text-ink-faint">—</span>
                    )}
                  </button>
                );
              })}
            </div>
          </QueryState>
        </div>
      </div>
    </div>
  );
}
