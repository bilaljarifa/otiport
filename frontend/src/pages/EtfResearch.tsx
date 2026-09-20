import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useForecastContext,
  useModelEvaluationDetail,
  useOhlc,
  useQuotes,
  useWatchlist,
  watchlistKey,
} from "../lib/queries";
import { addToWatchlist, removeFromWatchlist } from "../lib/portfolioApi";
import type { ChartPeriod } from "../lib/marketApi";
import { ETF_UNIVERSE } from "../lib/catalog";
import { money, percent, signedMoney, signedPercent } from "../lib/format";
import { CandlestickChart } from "../components/CandlestickChart";
import { ActualVsPredictedChart } from "../components/analytics/ActualVsPredictedChart";
import { QueryState } from "../components/QueryState";
import { FilterGroup } from "../components/FilterGroup";
import { NewsFeed } from "../components/NewsFeed";
import { buttonClass } from "../components/buttonStyles";

const PERIODS: { value: ChartPeriod; label: string }[] = [
  { value: "1mo", label: "1M" },
  { value: "3mo", label: "3M" },
  { value: "6mo", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "2y", label: "2Y" },
  { value: "5y", label: "5Y" },
];

type Tab = "overview" | "chart" | "forecast" | "news" | "risk" | "about";
const TABS: { value: Tab; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "chart", label: "Chart" },
  { value: "forecast", label: "Forecast" },
  { value: "news", label: "News" },
  { value: "risk", label: "Risk" },
  { value: "about", label: "About" },
];

export function EtfResearchPage() {
  const { ticker: rawTicker = "" } = useParams();
  const ticker = rawTicker.toUpperCase();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [period, setPeriod] = useState<ChartPeriod>("6mo");
  const queryClient = useQueryClient();

  const meta = useMemo(() => ETF_UNIVERSE.find((e) => e.ticker === ticker), [ticker]);
  const quote = useQuotes([ticker]);
  const ohlc = useOhlc(ticker, period);
  const watchlist = useWatchlist();
  const watchlistTickers = watchlist.data?.tickers ?? [];
  const isWatched = watchlistTickers.includes(ticker);

  function invalidateWatchlist() {
    void queryClient.invalidateQueries({ queryKey: watchlistKey });
    void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
  }
  const addMutation = useMutation({ mutationFn: addToWatchlist, onSuccess: invalidateWatchlist });
  const removeMutation = useMutation({ mutationFn: removeFromWatchlist, onSuccess: invalidateWatchlist });

  const q = quote.data?.quotes[ticker];
  const priceMissing = quote.data?.missing.includes(ticker);
  const lastBar = ohlc.data?.bars[ohlc.data.bars.length - 1];

  const evaluation = useModelEvaluationDetail(meta?.hasModel ? ticker : "");
  const forecast = useForecastContext(ticker, q?.price);

  if (!ticker) {
    return <p className="text-sm text-ink-muted">No ticker specified.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-baseline gap-3">
            <h1 className="font-mono text-2xl font-bold text-ink">{ticker}</h1>
            {meta && <span className="text-sm text-ink-muted">{meta.name}</span>}
          </div>
          {quote.isLoading ? (
            <span className="text-xs text-ink-faint">Loading…</span>
          ) : q ? (
            <div className="mt-1 flex items-baseline gap-3">
              <span className="font-mono text-xl font-bold text-ink">{money(q.price, 2)}</span>
              <span className={`font-mono text-sm font-semibold ${q.change_pct >= 0 ? "text-up" : "text-down"}`}>
                {signedMoney(q.change_abs, 2)} ({signedPercent(q.change_pct)})
              </span>
            </div>
          ) : (
            <span className="text-xs text-ink-faint">{priceMissing ? "Price unavailable" : ""}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => (isWatched ? removeMutation.mutate(ticker) : addMutation.mutate(ticker))}
            disabled={addMutation.isPending || removeMutation.isPending}
            className={buttonClass(isWatched ? "secondary" : "primary", "px-3 py-1.5")}
          >
            {isWatched ? "− Remove from watchlist" : "+ Add to watchlist"}
          </button>
          <button
            onClick={() => navigate(`/app/trading?ticker=${encodeURIComponent(ticker)}`)}
            className={buttonClass("accent", "px-3 py-1.5")}
          >
            Trade
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <FilterGroup value={tab} onChange={setTab} options={TABS} />
      </div>

      {tab === "overview" && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-md border border-line p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Current price</div>
            <div className="mt-1.5 font-mono text-xl font-bold text-ink">{q ? money(q.price, 2) : "—"}</div>
          </div>
          <div className="rounded-md border border-line p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Daily change</div>
            <div className={`mt-1.5 font-mono text-xl font-bold ${q && q.change_pct >= 0 ? "text-up" : "text-down"}`}>
              {q ? signedPercent(q.change_pct) : "—"}
            </div>
          </div>
          <div className="rounded-md border border-line p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Previous close</div>
            <div className="mt-1.5 font-mono text-xl font-bold text-ink">
              {q ? money(q.previous_close, 2) : "—"}
            </div>
          </div>
          <div className="rounded-md border border-line p-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Volume (latest bar)</div>
            <div className="mt-1.5 font-mono text-xl font-bold text-ink">
              {lastBar ? Math.round(lastBar.volume).toLocaleString() : "—"}
            </div>
          </div>
          {lastBar && (
            <>
              <div className="rounded-md border border-line p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Open</div>
                <div className="mt-1.5 font-mono text-lg font-bold text-ink">{money(lastBar.open, 2)}</div>
              </div>
              <div className="rounded-md border border-line p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">High</div>
                <div className="mt-1.5 font-mono text-lg font-bold text-ink">{money(lastBar.high, 2)}</div>
              </div>
              <div className="rounded-md border border-line p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Low</div>
                <div className="mt-1.5 font-mono text-lg font-bold text-ink">{money(lastBar.low, 2)}</div>
              </div>
              <div className="rounded-md border border-line p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Close</div>
                <div className="mt-1.5 font-mono text-lg font-bold text-ink">{money(lastBar.close, 2)}</div>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "chart" && (
        <div className="rounded-md border border-line">
          <div className="flex items-center gap-1 border-b border-line px-4 py-2">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`rounded px-2.5 py-1 text-xs font-semibold ${
                  period === p.value ? "bg-surface-alt text-ink" : "text-ink-muted hover:text-ink"
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
      )}

      {tab === "forecast" && (
        <QueryState
          isLoading={forecast.isLoading}
          isError={forecast.isError}
          error={forecast.error}
          onRetry={() => void forecast.refetch()}
        >
          {forecast.data && (
            <div className="flex flex-col gap-4">
              {!forecast.data.base_forecast.model_loaded && (
                <div className="rounded-md border border-line-strong bg-surface-alt px-4 py-2.5 text-sm text-ink-muted">
                  {forecast.data.base_forecast.note ?? "Model output unavailable for this ticker — showing historical data only."}
                </div>
              )}
              <div className="rounded-md border border-line">
                <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                  22-day return forecast
                </div>
                <div className="divide-y divide-line-soft">
                  <div className="flex items-center justify-between px-4 py-3">
                    <div>
                      <div className="text-sm font-semibold text-ink">Base Forecast</div>
                      <div className="text-xs text-ink-faint">Model output — LSTM prediction</div>
                    </div>
                    <span className="font-mono text-lg font-bold text-ink">
                      {forecast.data.base_forecast.predicted_return_22d != null
                        ? signedPercent(forecast.data.base_forecast.predicted_return_22d * 100)
                        : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between px-4 py-3">
                    <div>
                      <div className="text-sm font-semibold text-ink">News-Context Adjustment</div>
                      <div className="text-xs text-ink-faint">Sentiment × market-impact × confidence, capped ±2pp</div>
                    </div>
                    <span
                      className={`font-mono text-lg font-bold ${
                        forecast.data.news_context_forecast.adjustment_22d >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {signedPercent(forecast.data.news_context_forecast.adjustment_22d * 100)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between bg-surface-alt px-4 py-3">
                    <div>
                      <div className="text-sm font-bold text-ink">Context Forecast</div>
                      <div className="text-xs text-ink-faint">Base forecast + news-context adjustment</div>
                    </div>
                    <span
                      className={`font-mono text-xl font-bold ${
                        forecast.data.news_context_forecast.predicted_return_22d >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {signedPercent(forecast.data.news_context_forecast.predicted_return_22d * 100)}
                    </span>
                  </div>
                </div>
              </div>

              {evaluation.data?.evaluation.status === "ok" && (
                <div className="rounded-md border border-line p-4">
                  <div className="mb-2 text-sm font-bold text-ink">Historical model performance</div>
                  <div className="flex flex-wrap gap-6 text-sm">
                    <div>
                      <div className="text-xs text-ink-faint">Directional accuracy (test)</div>
                      <div className="font-mono font-semibold text-ink">
                        {evaluation.data.evaluation.test_metrics?.directional_accuracy != null
                          ? percent(evaluation.data.evaluation.test_metrics.directional_accuracy, 1)
                          : "—"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-ink-faint">Test MAE</div>
                      <div className="font-mono font-semibold text-ink">
                        {evaluation.data.evaluation.test_metrics?.mae.toFixed(4) ?? "—"}
                      </div>
                    </div>
                    <Link
                      to="/app/analytics"
                      className="ml-auto self-center text-xs font-semibold text-ink-muted underline underline-offset-2 hover:text-ink"
                    >
                      Full model evaluation →
                    </Link>
                  </div>
                </div>
              )}

              <p className="rounded-md border border-dashed border-line px-4 py-3 text-xs text-ink-faint">
                {forecast.data.disclaimer} Model output and news-context adjustments are estimates
                derived from historical data and are not guarantees of future returns.
              </p>
            </div>
          )}
        </QueryState>
      )}

      {tab === "news" && <NewsFeed ticker={ticker} />}

      {tab === "risk" && (
        <div className="flex flex-col gap-4">
          {evaluation.data?.evaluation.status === "ok" && evaluation.data.evaluation.test_series && (
            <div className="rounded-md border border-line">
              <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                Actual vs. predicted 22-day return (test period)
              </div>
              <div className="p-2">
                <ActualVsPredictedChart series={evaluation.data.evaluation.test_series} />
              </div>
            </div>
          )}
          {!meta?.hasModel && (
            <div className="rounded-md border border-dashed border-line px-4 py-6 text-center text-sm text-ink-muted">
              No trained forecasting model exists for {ticker} — it's tracked as a broad-market
              benchmark, not one of the 12 sector ETFs the LSTM models were trained on.
            </div>
          )}
          <div className="rounded-md border border-line p-4 text-sm text-ink-muted">
            Detailed portfolio-level risk analysis — volatility, Sharpe ratio, Value at Risk,
            correlation, and risk contribution — is computed for your actual holdings in the{" "}
            <Link to="/app/risk" className="font-semibold underline underline-offset-2 text-ink">
              Risk Center
            </Link>
            .
          </div>
        </div>
      )}

      {tab === "about" && (
        <div className="rounded-md border border-line p-4">
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-faint">Ticker</dt>
              <dd className="mt-1 font-mono font-semibold text-ink">{ticker}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-faint">Name</dt>
              <dd className="mt-1 font-semibold text-ink">{meta?.name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-faint">Region</dt>
              <dd className="mt-1 font-semibold text-ink">{meta?.region ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-faint">Forecasting model</dt>
              <dd className="mt-1 font-semibold text-ink">{meta?.hasModel ? "Trained LSTM available" : "Not modeled"}</dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-ink-faint">
            Part of Optiport's fixed ETF research universe — market data from Yahoo Finance, news
            from NewsAPI with FinBERT-based sentiment scoring.
          </p>
        </div>
      )}
    </div>
  );
}
