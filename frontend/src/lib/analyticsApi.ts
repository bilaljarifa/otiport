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

// ---------------------------------------------------------------------------
//  Model Evaluation — out-of-sample metrics for the existing 12 ETF LSTM
//  models. Read-only; never trains or retrains anything.
// ---------------------------------------------------------------------------

export interface PeriodInfo {
  start: string | null;
  end: string | null;
  rows: number;
}

export interface SplitMetrics {
  mae: number;
  rmse: number;
  mape: number | null;
  mape_observations: number;
  directional_accuracy: number | null;
  observations: number;
}

export interface ActualPredictedSeries {
  dates: string[];
  actual: number[];
  predicted: number[];
}

export interface TickerEvaluation {
  ticker: string;
  status: "ok" | "insufficient_data" | "model_unavailable" | "model_load_error";
  detail?: string | null;
  train_period?: PeriodInfo | null;
  validation_period?: PeriodInfo | null;
  test_period?: PeriodInfo | null;
  validation_metrics?: SplitMetrics | null;
  test_metrics?: SplitMetrics | null;
  validation_series?: ActualPredictedSeries | null;
  test_series?: ActualPredictedSeries | null;
}

export interface ModelEvaluationSummaryResponse {
  tickers: TickerEvaluation[];
  methodology_notes: string[];
}

export interface ModelEvaluationDetailResponse {
  evaluation: TickerEvaluation;
  methodology_notes: string[];
}

export function getModelEvaluationUniverse(): Promise<{ tickers: string[] }> {
  return apiRequest("/analytics/model-evaluation/universe");
}

export function getModelEvaluationSummary(): Promise<ModelEvaluationSummaryResponse> {
  return apiRequest("/analytics/model-evaluation/summary");
}

export function getModelEvaluationDetail(ticker: string): Promise<ModelEvaluationDetailResponse> {
  return apiRequest(`/analytics/model-evaluation/${encodeURIComponent(ticker)}`);
}

// ---------------------------------------------------------------------------
//  Backtesting — historical walk-forward simulation of the app's own
//  forecast + optimize strategy. Never a prediction of future performance.
// ---------------------------------------------------------------------------

export interface BacktestRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  strategy: Strategy;
  risk_free_rate: number;
  benchmark_ticker: string | null;
}

export interface EquityPoint {
  date: string;
  strategy_equity: number;
  benchmark_equity: number | null;
}

export interface TradeOut {
  date: string;
  ticker: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  notional: number;
}

export interface CurveStats {
  total_return_pct: number;
  annualized_return_pct: number;
  annualized_volatility_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  trading_days: number;
}

export interface BacktestResponse {
  inputs: {
    tickers: string[];
    start_date: string;
    end_date: string;
    initial_capital: number;
    strategy: string;
    risk_free_rate: number;
    benchmark_ticker: string | null;
  };
  equity_curve: EquityPoint[];
  rebalance_dates: string[];
  trades: TradeOut[];
  num_trades: number;
  winning_periods: number;
  losing_periods: number;
  flat_periods: number;
  win_rate_pct: number | null;
  strategy_metrics: CurveStats;
  benchmark_metrics: CurveStats | null;
  methodology_notes: string[];
}

export function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  return apiRequest<BacktestResponse>("/analytics/backtest", { method: "POST", body: req });
}

export type BacktestPhase =
  | "starting" | "loading_models" | "fetching_data" | "computing_features"
  | "forecasting" | "simulating" | "done";

export interface BacktestProgress {
  phase: BacktestPhase;
  completed: number;
  total: number;
  period_start: string | null;
  period_end: string | null;
}

export interface BacktestJobStatus {
  status: "running" | "done" | "error";
  progress: BacktestProgress;
  result: BacktestResponse | null;
  error: string | null;
}

/** Starts the same walk-forward simulation as `runBacktest` on a background
 * thread and returns immediately with a job id — pair with
 * `getBacktestJobStatus`, polled, for real progress instead of blocking on
 * one long request. */
export function startBacktestJob(req: BacktestRequest): Promise<{ job_id: string }> {
  return apiRequest<{ job_id: string }>("/analytics/backtest/start", { method: "POST", body: req });
}

export function getBacktestJobStatus(jobId: string): Promise<BacktestJobStatus> {
  return apiRequest<BacktestJobStatus>(`/analytics/backtest/status/${encodeURIComponent(jobId)}`);
}

// ---------------------------------------------------------------------------
//  Efficient frontier — real mean-variance frontier over the same LSTM
//  forecasts + historical covariance the optimizer/backtester use.
// ---------------------------------------------------------------------------

export interface EfficientFrontierRequest {
  tickers?: string[];
  risk_free_rate?: number;
  n_points?: number;
}

export interface EfficientFrontierResponse {
  returns: number[];
  volatilities: number[];
  sharpes: number[];
  max_sharpe_return: number;
  max_sharpe_volatility: number;
  min_vol_return: number;
  min_vol_volatility: number;
}

export function getEfficientFrontier(req: EfficientFrontierRequest = {}): Promise<EfficientFrontierResponse> {
  return apiRequest<EfficientFrontierResponse>("/efficient-frontier", { method: "POST", body: req });
}

// ---------------------------------------------------------------------------
//  Market regime — transparent trend/volatility classification over real
//  price history (backend/market_regime.py). Never a prediction.
// ---------------------------------------------------------------------------

export type Trend = "POSITIVE_TREND" | "NEGATIVE_TREND" | "NEUTRAL";
export type VolatilityRegime = "HIGH_VOLATILITY" | "NORMAL_VOLATILITY";

export interface RegimeSnapshot {
  trend: Trend;
  volatility_regime: VolatilityRegime;
  cumulative_return_pct: number;
  annualized_volatility_pct: number;
}

export interface RegimeTimelinePoint extends RegimeSnapshot {
  date: string;
}

export interface MarketRegimeResponse {
  ticker: string;
  as_of: string;
  current_regime: RegimeSnapshot;
  max_drawdown_pct: number;
  observations: number;
  timeline: RegimeTimelinePoint[];
  methodology: {
    trend_window_days: number;
    trend_threshold_pct: number;
    volatility_window_days: number;
    volatility_high_multiplier: number;
  };
}

export function getMarketRegime(ticker: string): Promise<MarketRegimeResponse> {
  return apiRequest<MarketRegimeResponse>(`/analytics/market-regime?ticker=${encodeURIComponent(ticker)}`);
}

// ---------------------------------------------------------------------------
//  Model Comparison Lab — LSTM vs. transparent non-ML baselines, same
//  chronological test split as Model Evaluation (backend/model_comparison.py).
// ---------------------------------------------------------------------------

export type ComparisonModelName = "naive" | "moving_average" | "linear_regression" | "lstm";

export interface ComparisonModelResult {
  model: ComparisonModelName;
  label: string;
  status: string;
  detail?: string | null;
  mae: number | null;
  rmse: number | null;
  mape: number | null;
  mape_observations: number;
  directional_accuracy: number | null;
  observations: number;
}

export interface ModelComparisonResponse {
  ticker: string;
  status: string;
  detail?: string | null;
  models: ComparisonModelResult[];
  test_period: { start: string; end: string; observations: number } | null;
  methodology: {
    target: string;
    forecast_horizon_days: number;
    sequence_length: number;
    train_fraction_pct: number;
    validation_fraction_pct: number;
    test_fraction_pct: number;
  } | null;
}

export function getModelComparison(ticker: string): Promise<ModelComparisonResponse> {
  return apiRequest<ModelComparisonResponse>(`/analytics/model-comparison/${encodeURIComponent(ticker)}`);
}
