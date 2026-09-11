import { apiRequest } from "./apiClient";

export interface Quote {
  ticker: string;
  price: number;
  previous_close: number;
  change_abs: number;
  change_pct: number;
}

export interface QuotesResponse {
  quotes: Record<string, Quote>;
  missing: string[];
}

export function getQuotes(tickers: string[]): Promise<QuotesResponse> {
  const query = encodeURIComponent(tickers.join(","));
  return apiRequest<QuotesResponse>(`/market/quotes?tickers=${query}`);
}

export interface OHLCBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OHLCResponse {
  ticker: string;
  period: string;
  bars: OHLCBar[];
}

export type ChartPeriod = "1mo" | "3mo" | "6mo" | "1y" | "2y" | "5y";

export function getOhlc(ticker: string, period: ChartPeriod): Promise<OHLCResponse> {
  return apiRequest<OHLCResponse>(
    `/market/ohlc?ticker=${encodeURIComponent(ticker)}&period=${period}`,
  );
}
