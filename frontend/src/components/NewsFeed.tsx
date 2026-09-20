import { useTickerNews, useTickerNewsSummary } from "../lib/queries";
import { QueryState } from "./QueryState";
import { Badge, ImpactBadge, sentimentTone } from "./Badge";
import { percent } from "../lib/format";
import type { SentimentLabel } from "../lib/newsApi";

/**
 * Sentiment summary + article list for one ticker — the News page's body,
 * extracted so the ETF Research page's NEWS tab can show the exact same
 * real pipeline output (`GET /news/{ticker}`, `GET /news/{ticker}/summary`)
 * instead of a second, parallel rendering of the same data.
 */
export function NewsFeed({ ticker }: { ticker: string }) {
  const summary = useTickerNewsSummary(ticker);
  const news = useTickerNews(ticker);

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-md border border-line p-4">
        <div className="mb-3 text-sm font-bold text-ink">Sentiment summary — {ticker}</div>
        <QueryState
          isLoading={summary.isLoading}
          isError={summary.isError}
          error={summary.error}
          onRetry={() => void summary.refetch()}
        >
          {summary.data && (
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={sentimentTone(summary.data.overall_sentiment as SentimentLabel)}>
                {summary.data.overall_sentiment}
              </Badge>
              <Badge tone={sentimentTone(summary.data.overall_market_impact as SentimentLabel)}>
                Impact: {summary.data.overall_market_impact}
              </Badge>
              <span className="text-sm text-ink-muted">
                {summary.data.news_count} articles ({summary.data.positive_news_count} positive,{" "}
                {summary.data.negative_news_count} negative, {summary.data.neutral_news_count} neutral)
              </span>
              <span className="text-sm text-ink-muted">
                Confidence: {percent(summary.data.average_confidence * 100, 0)}
              </span>
            </div>
          )}
        </QueryState>
      </div>

      <QueryState
        isLoading={news.isLoading}
        isError={news.isError}
        error={news.error}
        onRetry={() => void news.refetch()}
        isEmpty={news.data?.count === 0}
        emptyMessage={`No recent news found for ${ticker}.`}
      >
        <div className="flex flex-col gap-3">
          {news.data?.items.map((item, i) => (
            <div key={i} className="rounded-md border border-line p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <a
                  href={item.url ?? undefined}
                  target="_blank"
                  rel="noreferrer"
                  className={`font-semibold text-ink ${item.url ? "hover:underline" : "pointer-events-none"}`}
                >
                  {item.title}
                </a>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone={sentimentTone(item.sentiment.label)}>{item.sentiment.label}</Badge>
                  <ImpactBadge level={item.marketImpact.level} direction={item.marketImpact.direction} />
                </div>
              </div>
              {item.description && <p className="mt-2 text-sm text-ink-muted">{item.description}</p>}
              <div className="mt-2 text-xs text-ink-faint">
                {item.source}
                {item.publishedAt && ` · ${new Date(item.publishedAt).toLocaleString()}`}
              </div>
            </div>
          ))}
        </div>
      </QueryState>
    </div>
  );
}
