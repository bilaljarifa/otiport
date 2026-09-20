import { useState } from "react";
import { useMarketRegime } from "../../lib/queries";
import { ETF_UNIVERSE } from "../../lib/catalog";
import { percent, signedPercent } from "../../lib/format";
import { StatTile } from "../StatTile";
import { QueryState } from "../QueryState";
import { Badge } from "../Badge";
import { DivergingBarChart } from "../newsAnalytics/Charts";
import { SectionEyebrow } from "./SectionEyebrow";

const REGIME_TICKERS = [
  { ticker: "SPY", name: "S&P 500" },
  { ticker: "QQQ", name: "Nasdaq 100" },
  ...ETF_UNIVERSE.filter((e) => e.hasModel).map((e) => ({ ticker: e.ticker, name: e.name })),
];

const TREND_TONE: Record<string, string> = {
  POSITIVE_TREND: "bg-up-soft text-up",
  NEGATIVE_TREND: "bg-down-soft text-down",
  NEUTRAL: "bg-surface-alt text-ink-muted",
};

const VOL_TONE: Record<string, string> = {
  HIGH_VOLATILITY: "bg-down-soft text-down",
  NORMAL_VOLATILITY: "bg-surface-alt text-ink-muted",
};

function trendLabel(t: string): string {
  return t.replace(/_/g, " ");
}

/**
 * Transparent, disclosed-threshold trend/volatility classification over
 * real price history (`backend/market_regime.py`) — never a forecast of
 * the *next* regime, only a label for what the market has already done.
 */
export function MarketRegimePanel() {
  const [ticker, setTicker] = useState("SPY");
  const regime = useMarketRegime(ticker);
  const data = regime.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-md border border-line p-4">
        <SectionEyebrow>Configuration</SectionEyebrow>
        <div className="mb-1 mt-1 text-sm font-bold text-ink">Market Regime</div>
        <p className="mb-3 text-xs text-ink-faint">
          A transparent statistical read on already-observed price history — trend from the
          trailing 63-day return, volatility from the trailing 21-day realized volatility versus
          its own historical median. Fixed, disclosed thresholds; never a prediction of the next
          regime.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {REGIME_TICKERS.map((t) => (
            <button
              key={t.ticker}
              type="button"
              onClick={() => setTicker(t.ticker)}
              title={t.name}
              className={`rounded px-2.5 py-1 text-xs font-mono font-semibold ${
                ticker === t.ticker
                  ? "bg-ink-strong text-white"
                  : "border border-line-strong text-ink-muted hover:bg-surface-alt hover:text-ink"
              }`}
            >
              {t.ticker}
            </button>
          ))}
        </div>
      </div>

      <QueryState
        isLoading={regime.isLoading}
        isError={regime.isError}
        error={regime.error}
        onRetry={() => void regime.refetch()}
      >
        {data && (
          <>
            <SectionEyebrow>Current Regime — {data.ticker}</SectionEyebrow>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={TREND_TONE[data.current_regime.trend]}>{trendLabel(data.current_regime.trend)}</Badge>
              <Badge tone={VOL_TONE[data.current_regime.volatility_regime]}>
                {trendLabel(data.current_regime.volatility_regime)}
              </Badge>
              <span className="text-xs text-ink-faint">as of {data.as_of}</span>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatTile
                label={`${data.methodology.trend_window_days}D Return`}
                value={signedPercent(data.current_regime.cumulative_return_pct, 1)}
              />
              <StatTile
                label="Annualized Volatility"
                value={percent(data.current_regime.annualized_volatility_pct, 1)}
              />
              <StatTile label="Max Drawdown" value={signedPercent(data.max_drawdown_pct, 1)} />
              <StatTile label="Observations" value={String(data.observations)} />
            </div>

            <SectionEyebrow>Historical Regime Timeline</SectionEyebrow>
            <div className="rounded-md border border-line p-4">
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                {data.methodology.trend_window_days}-day trailing return, last {data.timeline.length} trading days
              </div>
              <DivergingBarChart
                points={data.timeline.map((p) => ({
                  label: p.date.slice(5),
                  value: p.cumulative_return_pct / 100,
                }))}
                min={-0.15}
                max={0.15}
                formatValue={(v) => `${(v * 100).toFixed(1)}%`}
              />
              <p className="mt-2 text-xs text-ink-faint">
                Green = positive trailing return, red = negative — not a forecast of what comes next.
              </p>
            </div>

            <details className="rounded-md border border-line p-4 text-sm">
              <summary className="cursor-pointer font-bold text-ink">Methodology &amp; limitations</summary>
              <ul className="mt-3 flex flex-col gap-2 text-xs text-ink-muted">
                <li className="flex gap-2">
                  <span className="text-ink-faint">•</span>
                  <span>
                    Trend: cumulative return over the trailing {data.methodology.trend_window_days} trading
                    days. Above +{data.methodology.trend_threshold_pct}% → Positive Trend, below −
                    {data.methodology.trend_threshold_pct}% → Negative Trend, otherwise Neutral.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-ink-faint">•</span>
                  <span>
                    Volatility: annualized realized volatility over the trailing{" "}
                    {data.methodology.volatility_window_days} trading days, compared to its own expanding
                    median since the start of the fetched window. Above {data.methodology.volatility_high_multiplier}×
                    that median → High Volatility.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-ink-faint">•</span>
                  <span>Purely descriptive of past price action — not a machine-learning model and not a prediction of the next regime.</span>
                </li>
              </ul>
            </details>
          </>
        )}
      </QueryState>
    </div>
  );
}
