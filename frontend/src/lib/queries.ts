import { useQuery } from "@tanstack/react-query";
import { getPortfolioSummary, getWatchlist } from "./portfolioApi";
import { getOhlc, getQuotes, type ChartPeriod } from "./marketApi";
import { getStats, listUsers } from "./adminApi";
import { getTickerNews, getTickerNewsSummary } from "./newsApi";
import { getAssistantStatus } from "./assistantApi";

/**
 * Centralized query keys/hooks — every page that needs the portfolio
 * summary or a set of quotes shares the same TanStack Query cache entry
 * instead of independently re-fetching, and gets the same short
 * revalidation window. Mirrors the intent of the Streamlit app's
 * `services/context.py` (fetch once per run, every page reads the same
 * snapshot) using TanStack Query's actual purpose-built mechanism for it.
 */

export function usePortfolioSummary() {
  return useQuery({
    queryKey: ["portfolio", "summary"],
    queryFn: getPortfolioSummary,
    staleTime: 5_000, // matches the backend's own settle/sync throttle window
  });
}

export const watchlistKey = ["portfolio", "watchlist"] as const;

export function useWatchlist() {
  return useQuery({
    queryKey: watchlistKey,
    queryFn: getWatchlist,
    staleTime: 5_000,
  });
}

export function useQuotes(tickers: string[]) {
  const key = [...tickers].sort().join(",");
  return useQuery({
    queryKey: ["market", "quotes", key],
    queryFn: () => getQuotes(tickers),
    enabled: tickers.length > 0,
    staleTime: 15_000, // backend quote_cache TTL is 20s — stay just under it
  });
}

export function useOhlc(ticker: string, period: ChartPeriod) {
  return useQuery({
    queryKey: ["market", "ohlc", ticker, period],
    queryFn: () => getOhlc(ticker, period),
    enabled: ticker.length > 0,
    staleTime: 55_000, // backend ohlc_cache TTL is 60s — stay just under it
  });
}

export const adminUsersKey = ["admin", "users"] as const;

export function useAdminUsers() {
  return useQuery({
    queryKey: adminUsersKey,
    queryFn: listUsers,
    staleTime: 5_000,
  });
}

export function useAdminStats() {
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: getStats,
    staleTime: 5_000,
  });
}

export function useTickerNews(ticker: string) {
  return useQuery({
    queryKey: ["news", "list", ticker],
    queryFn: () => getTickerNews(ticker),
    enabled: ticker.length > 0,
    staleTime: 15 * 60_000, // backend's analyzed-news cache is ~20 min — stay under it
    retry: false, // a missing/invalid NEWS_API_KEY returns 503 every time; retrying wastes calls
  });
}

export function useTickerNewsSummary(ticker: string) {
  return useQuery({
    queryKey: ["news", "summary", ticker],
    queryFn: () => getTickerNewsSummary(ticker),
    enabled: ticker.length > 0,
    staleTime: 15 * 60_000,
    retry: false,
  });
}

export function useAssistantStatus() {
  return useQuery({
    queryKey: ["assistant", "status"],
    queryFn: getAssistantStatus,
    staleTime: 60_000,
    retry: false,
  });
}
