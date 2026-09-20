import { apiRequest } from "./apiClient";

export interface BaseForecast {
  predicted_return_22d: number | null;
  used_return_22d: number;
  forecast_price: number | null;
  model_loaded: boolean;
  note: string | null;
  prediction_date: string | null;
}

export interface NewsContextForecast {
  predicted_return_22d: number;
  forecast_price: number | null;
  adjustment_22d: number;
  combined_news_signal: number;
  max_adjustment_22d: number;
}

export interface ForecastContext {
  ticker: string;
  current_price: number | null;
  base_forecast: BaseForecast;
  news_context_forecast: NewsContextForecast;
  potential_direction: "POTENTIAL_POSITIVE_IMPACT" | "POTENTIAL_NEGATIVE_IMPACT" | "NEUTRAL";
  news_features: Record<string, number>;
  disclaimer: string;
}

export function getForecastContext(ticker: string, currentPrice?: number): Promise<ForecastContext> {
  return apiRequest<ForecastContext>("/forecast/context", {
    method: "POST",
    body: { ticker, current_price: currentPrice ?? null },
  });
}
