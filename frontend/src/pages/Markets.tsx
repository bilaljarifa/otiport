import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useOhlc, useQuotes, useWatchlist, watchlistKey, useMarketImpact, useScreenerForecast,
} from "../lib/queries";
import { addToWatchlist, removeFromWatchlist } from "../lib/portfolioApi";
import type { ChartPeriod } from "../lib/marketApi";
import { money, signedMoney, signedPercent, percent } from "../lib/format";
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

type MarketsView = "chart" | "heatmap" | "screener";
const VIEWS: { value: MarketsView; label: string }[] = [
  { value: "chart", label: "Chart" },
  { value: "heatmap", label: "Heatmap" },
  { value: "screener", label: "Screener" },
];

export function MarketsPage() {
  const [view, setView] = useState<MarketsView>("chart");
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
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-ink">Markets</h1>
        <div className="inline-flex gap-1 rounded-md border border-line-strong bg-surface p-1">
          {VIEWS.map((v) => (
            <button
              key={v.value}
              type="button"
              onClick={() => setView(v.value)}
              className={`rounded px-3 py-1.5 text-xs font-semibold transition-colors ${
                view === v.value ? "bg-ink-strong text-white" : "text-ink-muted hover:bg-surface-alt hover:text-ink"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {view === "heatmap" && <MarketHeatmap onSelect={(t) => { setTicker(t); setView("chart"); }} />}
      {view === "screener" && <EtfScreener onSelect={(t) => { setTicker(t); setView("chart"); }} />}

      {view === "chart" && (
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
                to={`/app/research/${encodeURIComponent(ticker)}`}
                className={buttonClass("secondary", "px-3 py-1.5")}
              >
                Research
              </Link>
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
      )}
    </div>
  );
}

const HEATMAP_TICKERS = ETF_UNIVERSE.map((e) => e.ticker);

/** Tailwind's build-time scanner only picks up class names that appear as
 * literal strings in source — a runtime-built `bg-${color}/${n}` string
 * would compile to nothing. Every returned class here is one of these
 * fixed literals instead. */
function heatmapTone(changePct: number): string {
  const magnitude = Math.abs(changePct);
  if (magnitude < 0.3) return "bg-surface-alt text-ink-muted";
  if (changePct > 0) {
    if (magnitude < 1) return "bg-up/15 text-up";
    if (magnitude < 2) return "bg-up/35 text-up";
    if (magnitude < 4) return "bg-up/60 text-white";
    return "bg-up/85 text-white";
  }
  if (magnitude < 1) return "bg-down/15 text-down";
  if (magnitude < 2) return "bg-down/35 text-down";
  if (magnitude < 4) return "bg-down/60 text-white";
  return "bg-down/85 text-white";
}

/** Real ETF universe, colored by real daily change — same `/market/quotes`
 * data source as the Watchlist/chart view on this page, just laid out as a
 * grid instead of a list. No synthetic tiles: every cell is a real tracked
 * ETF, and a missing quote shows "unavailable" rather than a fabricated 0%. */
function MarketHeatmap({ onSelect }: { onSelect: (ticker: string) => void }) {
  const quotes = useQuotes(HEATMAP_TICKERS);

  return (
    <div className="rounded-md border border-line p-4">
      <div className="mb-3 text-sm font-bold text-ink">ETF universe — daily change</div>
      <QueryState
        isLoading={quotes.isLoading}
        isError={quotes.isError}
        error={quotes.error}
        onRetry={() => void quotes.refetch()}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {ETF_UNIVERSE.map((etf) => {
            const q = quotes.data?.quotes[etf.ticker];
            const missing = quotes.data?.missing.includes(etf.ticker);
            return (
              <button
                key={etf.ticker}
                type="button"
                onClick={() => onSelect(etf.ticker)}
                title={`${etf.name} · ${q ? money(q.price, 2) : "unavailable"}`}
                className={`flex flex-col items-start gap-1 rounded-md p-3 text-left transition-opacity hover:opacity-90 ${
                  q ? heatmapTone(q.change_pct) : "bg-surface-alt text-ink-faint"
                }`}
              >
                <span className="font-mono text-sm font-bold">{etf.ticker}</span>
                <span className="text-xs opacity-80">{etf.name}</span>
                <span className="font-mono text-xs font-semibold">
                  {q ? signedPercent(q.change_pct) : missing ? "unavailable" : "—"}
                </span>
              </button>
            );
          })}
        </div>
      </QueryState>
    </div>
  );
}

const SCREENER_TRAINED_TICKERS = ETF_UNIVERSE.filter((e) => e.hasModel).map((e) => e.ticker);

/** Real universe screener. Price/change come from `/market/quotes`;
 * historical return/volatility and the LSTM forecast come from the same
 * `/smart-invest` allocation response Analytics > Portfolio Optimizer
 * already shows (reused, not recomputed); news impact comes from the same
 * `/news/market-impact` pipeline News Analytics uses. Sharpe is a plain
 * derived ratio of those two already-real numbers, not a new estimate.
 * SPY/QQQ have no trained model, so forecast/vol/sharpe show "--" for them
 * rather than a misleading historical-only fallback. */
function EtfScreener({ onSelect }: { onSelect: (ticker: string) => void }) {
  const quotes = useQuotes(HEATMAP_TICKERS);
  const forecast = useScreenerForecast(SCREENER_TRAINED_TICKERS);
  const impact = useMarketImpact(HEATMAP_TICKERS);

  const forecastByTicker = new Map((forecast.data?.allocations ?? []).map((a) => [a.ticker, a]));
  const impactByTicker = new Map((impact.data?.tickers ?? []).map((t) => [t.ticker, t]));

  const isLoading = quotes.isLoading;

  return (
    <div className="rounded-md border border-line">
      <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
        ETF universe screener
      </div>
      <QueryState isLoading={isLoading} isError={quotes.isError} error={quotes.error} onRetry={() => void quotes.refetch()}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                <th className="px-4 py-2 font-semibold">Ticker</th>
                <th className="px-4 py-2 font-semibold">Name</th>
                <th className="px-4 py-2 font-semibold">Price</th>
                <th className="px-4 py-2 font-semibold">Daily Change</th>
                <th className="px-4 py-2 font-semibold">Return (YTD)</th>
                <th className="px-4 py-2 font-semibold">Volatility</th>
                <th className="px-4 py-2 font-semibold">Sharpe</th>
                <th className="px-4 py-2 font-semibold">Forecast (22d)</th>
                <th className="px-4 py-2 font-semibold">News Impact</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft font-mono">
              {ETF_UNIVERSE.map((etf) => {
                const q = quotes.data?.quotes[etf.ticker];
                const f = forecastByTicker.get(etf.ticker);
                const vol = f ? f.historical_volatility * 100 : null;
                const sharpe = f && vol && vol > 0 ? (f.ytd_return - 5) / vol : null;
                const imp = impactByTicker.get(etf.ticker);
                return (
                  <tr
                    key={etf.ticker}
                    onClick={() => onSelect(etf.ticker)}
                    className="cursor-pointer hover:bg-surface-alt"
                  >
                    <td className="px-4 py-2.5 font-sans font-semibold text-ink">{etf.ticker}</td>
                    <td className="px-4 py-2.5 font-sans text-xs text-ink-muted">{etf.name}</td>
                    <td className="px-4 py-2.5">{q ? money(q.price, 2) : "--"}</td>
                    <td className={`px-4 py-2.5 ${q ? (q.change_pct >= 0 ? "text-up" : "text-down") : ""}`}>
                      {q ? signedPercent(q.change_pct) : "--"}
                    </td>
                    <td className={`px-4 py-2.5 ${f ? (f.ytd_return >= 0 ? "text-up" : "text-down") : ""}`}>
                      {f ? signedPercent(f.ytd_return, 1) : etf.hasModel ? "…" : "--"}
                    </td>
                    <td className="px-4 py-2.5">{vol != null ? percent(vol, 1) : etf.hasModel ? "…" : "--"}</td>
                    <td className="px-4 py-2.5">{sharpe != null ? sharpe.toFixed(2) : etf.hasModel ? "…" : "--"}</td>
                    <td className={`px-4 py-2.5 ${f ? (f.predicted_return_capped >= 0 ? "text-up" : "text-down") : ""}`}>
                      {f ? signedPercent(f.predicted_return_capped, 1) : etf.hasModel ? "…" : "--"}
                    </td>
                    <td className={`px-4 py-2.5 ${imp ? (imp.weighted_sentiment >= 0 ? "text-up" : "text-down") : ""}`}>
                      {imp ? imp.weighted_sentiment.toFixed(2) : impact.isLoading ? "…" : "--"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="border-t border-line-soft px-4 py-2 text-xs text-ink-faint">
          Sharpe = (YTD return − 5% risk-free) / volatility, computed here from the same real
          historical return/volatility shown above — not a separate estimate. SPY/QQQ have no
          trained forecasting model, so forecast-derived columns show "--" for them.
        </p>
      </QueryState>
    </div>
  );
}
