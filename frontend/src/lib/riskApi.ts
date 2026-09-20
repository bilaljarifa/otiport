import { apiRequest } from "./apiClient";

export interface PositionRisk {
  ticker: string;
  weight_pct: number;
  market_value: number;
  risk_contribution_pct: number;
}

export interface VarStats {
  confidence: number;
  var_pct: number;
  cvar_pct: number;
  observations: number;
  var_dollar: number;
  cvar_dollar: number;
}

export interface RegionExposure {
  region: string;
  weight_pct: number;
}

export interface CorrelationMatrix {
  tickers: string[];
  values: number[][];
}

export interface PortfolioRisk {
  status: "ok" | "empty";
  detail?: string | null;
  invested_value: number;
  cash: number;
  cash_pct: number;
  lookback_days: number | null;
  volatility_pct: number | null;
  annualized_return_pct: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  var: VarStats | null;
  beta: number | null;
  benchmark_ticker: string | null;
  concentration_hhi: number | null;
  diversification_score: number | null;
  positions: PositionRisk[];
  exposure_by_region: RegionExposure[];
  correlation_matrix: CorrelationMatrix | null;
  methodology_notes: string[];
}

export function getPortfolioRisk(benchmark = "SPY"): Promise<PortfolioRisk> {
  return apiRequest<PortfolioRisk>(`/risk/portfolio?benchmark=${encodeURIComponent(benchmark)}`);
}
