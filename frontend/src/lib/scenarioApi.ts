import { apiRequest } from "./apiClient";
import type { PortfolioRisk } from "./riskApi";

export interface ScenarioHoldingInput {
  ticker: string;
  dollar_value: number;
}

export interface ScenarioRequest {
  holdings: ScenarioHoldingInput[];
  cash: number;
  benchmark_ticker?: string | null;
  risk_free_rate?: number;
}

/** Same shape as the Risk Center's `PortfolioRisk` plus a forecast-based
 * expected return — this endpoint reuses the identical risk pipeline, just
 * against a hypothetical (never persisted) set of holdings instead of the
 * caller's real ones. */
export interface ScenarioResult extends PortfolioRisk {
  expected_return_pct: number | null;
}

export function analyzeScenario(req: ScenarioRequest): Promise<ScenarioResult> {
  return apiRequest<ScenarioResult>("/analytics/scenario", { method: "POST", body: req });
}
