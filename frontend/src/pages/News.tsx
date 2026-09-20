import { useMemo, useState, type ReactNode } from "react";
import { ETF_UNIVERSE } from "../lib/catalog";
import { NewsFeed } from "../components/NewsFeed";
import { QueryState } from "../components/QueryState";
import { StatTile } from "../components/StatTile";
import { FilterGroup } from "../components/FilterGroup";
import { Badge, ImpactBadge, sentimentTone } from "../components/Badge";
import { useNewsAnalytics, useForecastContext } from "../lib/queries";
import { percent, signedPercent } from "../lib/format";
import { DivergingBarChart, ScatterPlot, SimpleBarChart, classifyChartDensity } from "../components/newsAnalytics/Charts";
import type { TrendRangeLabel } from "../lib/newsAnalyticsApi";

function scoreValue(v: number | null | undefined, decimals = 2): string {
  return v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(decimals);
}

function SectionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-line">
      <div className="border-b border-line px-4 py-2.5">
        <div className="text-sm font-bold text-ink">{title}</div>
        {subtitle && <div className="mt-0.5 text-xs text-ink-faint">{subtitle}</div>}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function InsufficientData({ reason }: { reason?: string | null }) {
  return (
    <div className="rounded-md border border-dashed border-line px-4 py-8 text-center text-sm text-ink-muted">
      {reason ?? "Not enough data to compute this yet."}
    </div>
  );
}

export function NewsPage() {
  const [ticker, setTicker] = useState("SPY");
  const meta = ETF_UNIVERSE.find((e) => e.ticker === ticker);
  const analytics = useNewsAnalytics(ticker);
  const forecast = useForecastContext(ticker);
  const data = analytics.data;

  const availableRanges = useMemo(
    () => data?.sentiment_trend.ranges.filter((r) => r.available) ?? [],
    [data],
  );
  const [selectedRange, setSelectedRange] = useState<TrendRangeLabel | null>(null);
  const activeRange =
    availableRanges.find((r) => r.range === selectedRange) ?? availableRanges[availableRanges.length - 1];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-ink">News Impact Analytics</h1>
        <p className="mt-1 text-xs text-ink-faint">
          Quantitative read on real news coverage for one ticker — sentiment, volume, market impact and
          its observed association with price, all computed from the live NewsAPI pipeline.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {ETF_UNIVERSE.map((etf) => (
          <button
            key={etf.ticker}
            onClick={() => {
              setTicker(etf.ticker);
              setSelectedRange(null);
            }}
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

      <QueryState
        isLoading={analytics.isLoading}
        isError={analytics.isError}
        error={analytics.error}
        onRetry={() => void analytics.refetch()}
      >
        {data && (
          <>
            {/* 1. Overview / KPIs */}
            <SectionCard title="Overview">
              {data.overview.status === "empty" ? (
                <InsufficientData reason={`No recent news found for ${ticker}.`} />
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                  <StatTile label="Articles analyzed" value={String(data.overview.articles_analyzed)} />
                  <StatTile label="Positive" value={percent(data.overview.positive_pct ?? 0, 0)} />
                  <StatTile label="Neutral" value={percent(data.overview.neutral_pct ?? 0, 0)} />
                  <StatTile label="Negative" value={percent(data.overview.negative_pct ?? 0, 0)} />
                  <StatTile
                    label="Avg. sentiment"
                    value={scoreValue(data.overview.average_sentiment_score)}
                    hint="unweighted, -1 to +1"
                  />
                  <StatTile
                    label="Aggregate impact score"
                    value={scoreValue(data.overview.aggregate_impact_score)}
                    hint="recency+impact weighted"
                  />
                </div>
              )}
            </SectionCard>

            {/* 2. Sentiment distribution */}
            <SectionCard title="Sentiment Distribution" subtitle="Article-level sentiment from the pipeline">
              {data.sentiment_distribution.status === "empty" ? (
                <InsufficientData />
              ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {data.sentiment_distribution.distribution.map((b) => (
                    <div key={b.label} className="rounded-md border border-line-soft p-3">
                      <Badge tone={sentimentTone(b.label)}>{b.label}</Badge>
                      <div className="mt-2 font-mono text-lg font-bold text-ink">{percent(b.pct, 0)}</div>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-alt">
                        <div
                          className={`h-full rounded-full ${
                            b.label === "POSITIVE" ? "bg-up" : b.label === "NEGATIVE" ? "bg-down" : "bg-ink-strong"
                          }`}
                          style={{ width: `${Math.min(b.pct, 100)}%` }}
                        />
                      </div>
                      <div className="mt-2 text-xs text-ink-muted">
                        {b.count} article{b.count === 1 ? "" : "s"}
                        {b.average_score != null && ` · avg score ${b.average_score.toFixed(2)}`}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>

            {/* 3. Sentiment trend + volume over time */}
            <SectionCard
              title="Sentiment &amp; Volume Trend"
              subtitle={
                data.sentiment_trend.status === "ok" && activeRange
                  ? `${activeRange.range} selected · ~${(data.sentiment_trend.data_span_hours ?? 0).toFixed(1)}h of real coverage · ${activeRange.points.length} observation${activeRange.points.length === 1 ? "" : "s"}`
                  : undefined
              }
            >
              {data.sentiment_trend.status !== "ok" || availableRanges.length === 0 ? (
                <InsufficientData reason={data.sentiment_trend.reason ?? "Not enough dated articles for a trend."} />
              ) : (
                <div className="flex flex-col gap-4">
                  <FilterGroup
                    value={activeRange?.range ?? availableRanges[0].range}
                    onChange={(v) => setSelectedRange(v)}
                    options={availableRanges.map((r) => ({ value: r.range, label: r.range }))}
                  />
                  {activeRange && (
                    <>
                      {classifyChartDensity(activeRange.points.length) === "sparse" && (
                        <div className="rounded-md border border-dashed border-line bg-surface-alt px-3 py-2 text-xs text-ink-muted">
                          Limited historical coverage — the available news history does not span the full{" "}
                          {activeRange.range} window selected. Showing the {activeRange.points.length} real observation
                          {activeRange.points.length === 1 ? "" : "s"} on record, not an interpolated trend.
                        </div>
                      )}
                      <div>
                        <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                          Average sentiment per bucket
                        </div>
                        <DivergingBarChart
                          points={activeRange.points.map((p) => ({
                            label: p.bucket.slice(5),
                            value: p.average_sentiment,
                            count: p.article_count,
                            tooltip: `${p.bucket}: ${scoreValue(p.average_sentiment)} avg sentiment (${p.article_count} article${p.article_count === 1 ? "" : "s"})`,
                          }))}
                        />
                      </div>
                      <div>
                        <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                          Article volume per bucket
                        </div>
                        <SimpleBarChart
                          points={activeRange.points.map((p) => ({
                            label: p.bucket.slice(5),
                            value: p.article_count,
                            tooltip: `${p.bucket}: ${p.article_count} article${p.article_count === 1 ? "" : "s"}`,
                          }))}
                        />
                      </div>
                    </>
                  )}
                </div>
              )}
            </SectionCard>

            {/* 4. Volume analysis */}
            <SectionCard title="News Volume Analysis">
              {data.volume_analysis.status !== "ok" ? (
                <InsufficientData reason={data.volume_analysis.reason} />
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <StatTile
                      label={`Current period (${data.volume_analysis.current_period_days}d)`}
                      value={String(data.volume_analysis.current_period_count ?? 0)}
                    />
                    {data.volume_analysis.previous_period_available ? (
                      <>
                        <StatTile
                          label="Previous period"
                          value={String(data.volume_analysis.previous_period_count ?? 0)}
                        />
                        <StatTile
                          label="Change"
                          value={
                            data.volume_analysis.pct_change != null
                              ? signedPercent(data.volume_analysis.pct_change, 1)
                              : "—"
                          }
                          delta={
                            data.volume_analysis.pct_change != null
                              ? { value: signedPercent(data.volume_analysis.pct_change, 1), positive: data.volume_analysis.pct_change >= 0 }
                              : null
                          }
                        />
                      </>
                    ) : (
                      <div className="col-span-2 flex items-center rounded-md border border-dashed border-line px-3 py-2 text-xs text-ink-muted">
                        {data.volume_analysis.insufficient_history_reason}
                      </div>
                    )}
                    <StatTile label="Data span" value={`${data.volume_analysis.data_span_days}d`} />
                  </div>
                  <SimpleBarChart points={data.volume_analysis.daily_series.map((p) => ({ label: p.date.slice(5), value: p.count }))} />
                </div>
              )}
            </SectionCard>

            {/* 5. Market impact score */}
            <SectionCard
              title="Market Impact Score"
              subtitle="Existing recency+impact-weighted aggregate, scale -1 (max negative) to +1 (max positive)"
            >
              {data.market_impact.status === "empty" ? (
                <InsufficientData />
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <StatTile label="Aggregate score" value={scoreValue(data.market_impact.aggregate_score)} />
                    <StatTile
                      label="Overall read"
                      value={(data.market_impact.overall_market_impact ?? "—").replace(/_/g, " ")}
                    />
                    <StatTile
                      label="Avg. recency weight"
                      value={data.market_impact.average_recency_weight?.toFixed(2) ?? "—"}
                      hint="0-1, 6h half-life"
                    />
                    <StatTile
                      label="Avg. article impact"
                      value={data.market_impact.average_article_impact_score?.toFixed(2) ?? "—"}
                      hint="0-1 magnitude"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between text-xs text-ink-muted">
                      <span>Positive contribution</span>
                      <span className="font-mono text-up">
                        +{(data.market_impact.positive_contribution ?? 0).toFixed(3)}
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
                      <div
                        className="h-full rounded-full bg-up"
                        style={{ width: `${Math.min((data.market_impact.positive_contribution ?? 0) * 100, 100)}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-xs text-ink-muted">
                      <span>Negative contribution</span>
                      <span className="font-mono text-down">
                        {(data.market_impact.negative_contribution ?? 0).toFixed(3)}
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
                      <div
                        className="h-full rounded-full bg-down"
                        style={{ width: `${Math.min(Math.abs(data.market_impact.negative_contribution ?? 0) * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </SectionCard>

            {/* 6. Top impactful news */}
            <SectionCard title="Top Impactful News" subtitle="Ranked by the existing per-article impact score">
              {data.top_news.status === "empty" ? (
                <InsufficientData />
              ) : (
                <div className="flex flex-col gap-3">
                  {data.top_news.items.map((item, i) => (
                    <div key={i} className="rounded-md border border-line p-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="flex items-start gap-2">
                          <span className="mt-0.5 font-mono text-xs font-bold text-ink-faint">#{i + 1}</span>
                          <a
                            href={item.url ?? undefined}
                            target="_blank"
                            rel="noreferrer"
                            className={`font-semibold text-ink ${item.url ? "hover:underline" : "pointer-events-none"}`}
                          >
                            {item.title}
                          </a>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <Badge tone={sentimentTone(item.sentiment.label)}>{item.sentiment.label}</Badge>
                          <ImpactBadge level={item.marketImpact.level} direction={item.marketImpact.direction} />
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-faint">
                        <span>{item.source}</span>
                        {item.publishedAt && <span>{new Date(item.publishedAt).toLocaleString()}</span>}
                        <span>Impact score: {item.impact_score.toFixed(2)}</span>
                        <span>Recency weight: {item.recency_weight.toFixed(2)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>

            {/* 7. News vs price movement */}
            <SectionCard title="News vs. Price Movement" subtitle="Observed historical association — not a causal claim">
              {data.news_vs_price.status !== "ok" ? (
                <InsufficientData reason={data.news_vs_price.reason} />
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <StatTile label="Observations" value={String(data.news_vs_price.observation_count ?? 0)} />
                    <StatTile
                      label="Correlation coefficient"
                      value={
                        data.news_vs_price.correlation_coefficient != null
                          ? data.news_vs_price.correlation_coefficient.toFixed(3)
                          : "n/a"
                      }
                      hint="Pearson, daily sentiment vs. return"
                    />
                  </div>
                  <ScatterPlot
                    points={data.news_vs_price.observations.map((o) => ({
                      x: o.sentiment,
                      y: o.daily_return_pct,
                      label: o.date,
                    }))}
                  />
                  <p className="text-xs text-ink-faint">{data.news_vs_price.methodology}</p>
                </div>
              )}
            </SectionCard>

            {/* 8. Forecast + news contribution */}
            <SectionCard
              title="Forecast + News Contribution"
              subtitle="Base LSTM forecast vs. the news-adjusted forecast, using the existing forecast-context pipeline"
            >
              <QueryState
                isLoading={forecast.isLoading}
                isError={forecast.isError}
                error={forecast.error}
                onRetry={() => void forecast.refetch()}
              >
                {forecast.data && !forecast.data.base_forecast.model_loaded ? (
                  <InsufficientData
                    reason={
                      forecast.data.base_forecast.note ??
                      `No trained forecasting model for ${ticker} — it's tracked as a broad-market benchmark.`
                    }
                  />
                ) : (
                  forecast.data && (
                    <div className="flex flex-col gap-4">
                      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
                        <StatTile
                          label="Base LSTM forecast (22d)"
                          value={signedPercent((forecast.data.base_forecast.used_return_22d ?? 0) * 100, 2)}
                        />
                        <span className="text-center text-lg text-ink-faint sm:mx-1">+</span>
                        <StatTile
                          label="News adjustment"
                          value={signedPercent((forecast.data.news_context_forecast.adjustment_22d ?? 0) * 100, 2)}
                          hint={`max ±${(forecast.data.news_context_forecast.max_adjustment_22d * 100).toFixed(1)}pp`}
                        />
                        <span className="text-center text-lg text-ink-faint sm:mx-1">=</span>
                        <StatTile
                          label="News-context forecast (22d)"
                          value={signedPercent((forecast.data.news_context_forecast.predicted_return_22d ?? 0) * 100, 2)}
                        />
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                        <Badge tone={sentimentTone(forecast.data.potential_direction === "POTENTIAL_NEGATIVE_IMPACT" ? "NEGATIVE" : forecast.data.potential_direction === "POTENTIAL_POSITIVE_IMPACT" ? "POSITIVE" : "NEUTRAL")}>
                          {forecast.data.potential_direction.replace(/_/g, " ")}
                        </Badge>
                        <span>Combined news signal: {forecast.data.news_context_forecast.combined_news_signal.toFixed(3)}</span>
                      </div>
                      <p className="text-xs text-ink-faint">{forecast.data.disclaimer}</p>
                    </div>
                  )
                )}
              </QueryState>
            </SectionCard>

            {/* 9. News impact history */}
            <SectionCard title="News Impact History" subtitle="Per-day aggregate impact score across the available window">
              {data.impact_history.status !== "ok" ? (
                <InsufficientData reason={data.impact_history.reason} />
              ) : (
                <DivergingBarChart
                  points={data.impact_history.points.map((p) => ({
                    label: p.date.slice(5),
                    value: p.aggregate_impact_score,
                    count: p.article_count,
                  }))}
                  height={160}
                />
              )}
            </SectionCard>

            {/* 10 & 11. Methodology + limitations */}
            <details className="rounded-md border border-line p-4 text-sm">
              <summary className="cursor-pointer font-bold text-ink">Methodology &amp; limitations</summary>
              <div className="mt-3 flex flex-col gap-4 text-xs text-ink-muted">
                <div>
                  <div className="mb-1.5 font-semibold text-ink">Pipeline</div>
                  <ol className="flex flex-col gap-1.5">
                    {[
                      "NewsAPI /v2/everything — queried ticker → company name → contextual variants, broadest-first, up to 30 days back.",
                      "Preprocessing — HTML stripped, text cleaned, near-duplicate articles removed by URL/title.",
                      "Sentiment analysis — FinBERT where available, with an automatic lexicon-based fallback scorer.",
                      "Market impact scoring — sentiment confidence combined with keyword-based materiality (earnings, guidance, M&A, litigation, etc.).",
                      "Recency weighting — exponential decay, 6-hour half-life.",
                      "Aggregation — each article contributes signed_sentiment × recency_weight × impact_score to a weighted average.",
                      "Forecast adjustment — the aggregate news signal nudges the base LSTM 22-day return forecast, capped at ±2 percentage points.",
                    ].map((step, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="font-mono font-semibold text-ink-faint">{i + 1}.</span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
                <div>
                  <div className="mb-1.5 font-semibold text-ink">Limitations</div>
                  <ul className="flex flex-col gap-1.5">
                    {[
                      "News coverage from a single API may be incomplete — absence of a headline does not mean absence of news.",
                      "Automated sentiment classification can misjudge tone, sarcasm or context.",
                      "Any statistical association shown here is historical, not causal, and not predictive of future price action.",
                      "The news impact score is an analytical signal, not a guaranteed forecast.",
                      "All statistics depend on the sample and time period actually available for this ticker at the time of the request.",
                    ].map((note, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-ink-faint">•</span>
                        <span>{note}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </details>
          </>
        )}
      </QueryState>

      <details className="rounded-md border border-line p-4">
        <summary className="cursor-pointer text-sm font-bold text-ink">Recent articles ({meta?.name ?? ticker})</summary>
        <div className="mt-4">
          <NewsFeed ticker={ticker} />
        </div>
      </details>
    </div>
  );
}
