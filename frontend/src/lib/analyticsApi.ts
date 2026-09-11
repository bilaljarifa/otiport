import { apiRequest } from "./apiClient";

export type Strategy = "max_sharpe" | "min_volatility" | "risk_parity" | "equal_weight";

export interface SmartInvestRequest {
  tickers?: string[];
  risk_free_rate?: number;
  strategy?: Strategy;
  investment_amount?: number | null;
  include_charts?: boolean;
}

export interface ETFAllocation {
  ticker: string;
  name: string;
  region: string;
  weight_percent: number;
  amount: number | null;
  predicted_return: number;
  predicted_return_capped: number;
  historical_volatility: number;
  ytd_return: number;
  recommendation: string;
}

export interface PortfolioMetrics {
  expected_annual_return: number;
  expected_annual_return_percent: number;
  expected_annual_return_capped: number;
  annual_volatility: number;
  annual_volatility_percent: number;
  sharpe_ratio: number;
  diversification_score: number;
  portfolio_ytd_return: number;
}

export interface GeographicAllocation {
  region: string;
  allocation_percent: number;
}

export interface SmartInvestResponse {
  success: boolean;
  strategy_used: string;
  allocations: ETFAllocation[];
  portfolio_metrics: PortfolioMetrics;
  geographic_allocation: GeographicAllocation[];
  investment_amount: number | null;
  recommendation_summary: string;
  top_picks: string[];
}

export function smartInvest(req: SmartInvestRequest): Promise<SmartInvestResponse> {
  return apiRequest<SmartInvestResponse>("/smart-invest", {
    method: "POST",
    body: { ...req, include_charts: false },
  });
}
