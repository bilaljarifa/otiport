import { apiRequest } from "./apiClient";

export type SentimentLabel = "POSITIVE" | "NEGATIVE" | "NEUTRAL";
export type ImpactLevel = "LOW" | "MEDIUM" | "HIGH";

export interface Sentiment {
  label: SentimentLabel;
  score: number;
}

export interface MarketImpact {
  direction: SentimentLabel;
  level: ImpactLevel;
  confidence: number;
}

export interface NewsItem {
  title: string;
  description: string;
  source: string;
  url: string | null;
  publishedAt: string | null;
  sentiment: Sentiment;
  marketImpact: MarketImpact;
  recencyWeight: number;
}

export interface NewsListResponse {
  ticker: string;
  items: NewsItem[];
  count: number;
}

export function getTickerNews(ticker: string): Promise<NewsListResponse> {
  return apiRequest<NewsListResponse>(`/news/${encodeURIComponent(ticker)}`);
}

export interface NewsSummary {
  ticker: string;
  news_count: number;
  positive_news_count: number;
  negative_news_count: number;
  neutral_news_count: number;
  weighted_sentiment: number;
  overall_sentiment: string;
  overall_market_impact: string;
  overall_confidence: number;
  average_confidence: number;
}

export function getTickerNewsSummary(ticker: string): Promise<NewsSummary> {
  return apiRequest<NewsSummary>(`/news/${encodeURIComponent(ticker)}/summary`);
}
