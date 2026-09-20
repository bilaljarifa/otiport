import { apiRequest } from "./apiClient";
import type { MarketImpact, Sentiment } from "./newsApi";

export type DataStatus = "ok" | "empty" | "insufficient_data";
export type TrendRangeLabel = "24H" | "3D" | "7D" | "30D";

export interface NewsOverview {
  status: "ok" | "empty";
  articles_analyzed: number;
  positive_pct: number | null;
  neutral_pct: number | null;
  negative_pct: number | null;
  average_sentiment_score: number | null;
  aggregate_impact_score: number | null;
  overall_sentiment: string;
  overall_market_impact: string;
}

export interface SentimentBucket {
  label: "POSITIVE" | "NEUTRAL" | "NEGATIVE";
  count: number;
  pct: number;
  average_score: number | null;
}

export interface SentimentDistribution {
  status: "ok" | "empty";
  total: number;
  distribution: SentimentBucket[];
}

export interface TrendPoint {
  bucket: string;
  article_count: number;
  average_sentiment: number;
}

export interface TrendRange {
  range: TrendRangeLabel;
  available: boolean;
  reason?: string | null;
  article_count?: number | null;
  points: TrendPoint[];
}

export interface SentimentTrend {
  status: "ok" | "insufficient_data";
  reason?: string | null;
  data_span_hours?: number | null;
  ranges: TrendRange[];
}

export interface VolumeDailyPoint {
  date: string;
  count: number;
}

export interface VolumeAnalysis {
  status: "ok" | "insufficient_data";
  reason?: string | null;
  daily_series: VolumeDailyPoint[];
  data_span_days?: number | null;
  current_period_days?: number | null;
  current_period_count?: number | null;
  previous_period_available: boolean;
  previous_period_count?: number | null;
  pct_change?: number | null;
  insufficient_history_reason?: string | null;
}

export interface MarketImpactBreakdown {
  status: "ok" | "empty";
  aggregate_score: number | null;
  scale_min?: number | null;
  scale_max?: number | null;
  overall_sentiment?: string | null;
  overall_market_impact?: string | null;
  positive_contribution?: number | null;
  negative_contribution?: number | null;
  average_recency_weight?: number | null;
  average_article_impact_score?: number | null;
  articles_considered?: number | null;
}

export interface TopNewsItem {
  title: string;
  source: string;
  url: string | null;
  publishedAt: string | null;
  sentiment: Sentiment;
  marketImpact: MarketImpact;
  impact_score: number;
  recency_weight: number;
}

export interface TopNews {
  status: "ok" | "empty";
  items: TopNewsItem[];
}

export interface PriceObservation {
  date: string;
  sentiment: number;
  article_count: number;
  daily_return_pct: number;
}

export interface NewsVsPrice {
  status: "ok" | "insufficient_data";
  reason?: string | null;
  methodology?: string | null;
  observation_count?: number | null;
  correlation_coefficient?: number | null;
  observations: PriceObservation[];
}

export interface ImpactHistoryPoint {
  date: string;
  article_count: number;
  aggregate_impact_score: number;
  overall_market_impact: string;
}

export interface ImpactHistory {
  status: "ok" | "insufficient_data";
  reason?: string | null;
  points: ImpactHistoryPoint[];
}

export interface NewsAnalytics {
  ticker: string;
  overview: NewsOverview;
  sentiment_distribution: SentimentDistribution;
  sentiment_trend: SentimentTrend;
  volume_analysis: VolumeAnalysis;
  market_impact: MarketImpactBreakdown;
  top_news: TopNews;
  news_vs_price: NewsVsPrice;
  impact_history: ImpactHistory;
}

export function getNewsAnalytics(ticker: string): Promise<NewsAnalytics> {
  return apiRequest<NewsAnalytics>(`/news/${encodeURIComponent(ticker)}/analytics`);
}
