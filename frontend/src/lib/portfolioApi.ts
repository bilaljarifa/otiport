import { apiRequest } from "./apiClient";

export interface Account {
  cash: number;
  initial_cash: number;
  created_at: string;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_price: number;
}

export type OrderSide = "BUY" | "SELL";
export type OrderType = "MARKET" | "LIMIT";
export type OrderStatus = "OPEN" | "FILLED" | "CANCELLED" | "REJECTED";

export interface Order {
  id: number;
  ticker: string;
  side: OrderSide;
  quantity: number;
  type: OrderType;
  limit_price: number | null;
  status: OrderStatus;
  fill_price: number | null;
  reject_reason: string | null;
  created_at: string;
  filled_at: string | null;
}

export interface Transaction {
  id: number;
  type: string;
  ticker: string | null;
  quantity: number | null;
  price: number | null;
  amount: number;
  note: string;
  created_at: string;
}

export type AlertDirection = "above" | "below";
export type AlertStatus = "ACTIVE" | "TRIGGERED";

export interface Alert {
  id: number;
  ticker: string;
  direction: AlertDirection;
  threshold: number;
  note: string;
  status: AlertStatus;
  created_at: string;
  triggered_at: string | null;
  triggered_price: number | null;
}

export interface PortfolioSummary {
  account: Account;
  positions: Position[];
  orders: Order[];
  transactions: Transaction[];
  watchlist: string[];
  alerts: Alert[];
}

export function getPortfolioSummary(): Promise<PortfolioSummary> {
  return apiRequest<PortfolioSummary>("/portfolio/summary");
}

export function settlePortfolio(): Promise<void> {
  return apiRequest<void>("/portfolio/settle", { method: "POST" });
}

export interface AddAlertRequest {
  ticker: string;
  direction: AlertDirection;
  threshold: number;
  note?: string;
}

/** Price alerts — evaluated against fresh quotes automatically every time
 * `settlePortfolio()` runs (see `AppShell`'s 60s poll and
 * `backend/crud.py::settle`), not a separate push/notification system. */
export function getAlerts(): Promise<Alert[]> {
  return apiRequest<Alert[]>("/portfolio/alerts");
}

export function addAlert(req: AddAlertRequest): Promise<Alert> {
  return apiRequest<Alert>("/portfolio/alerts", { method: "POST", body: req });
}

export function removeAlert(alertId: number): Promise<void> {
  return apiRequest<void>(`/portfolio/alerts/${alertId}`, { method: "DELETE" });
}

export function resetAlert(alertId: number): Promise<Alert> {
  return apiRequest<Alert>(`/portfolio/alerts/${alertId}/reset`, { method: "POST" });
}

export function resetAccount(): Promise<void> {
  return apiRequest<void>("/portfolio/reset", { method: "POST" });
}

export interface PlaceOrderRequest {
  ticker: string;
  side: OrderSide;
  quantity: number;
  order_type: OrderType;
  limit_price?: number | null;
}

export function placeOrder(req: PlaceOrderRequest): Promise<Order> {
  return apiRequest<Order>("/portfolio/orders", { method: "POST", body: req });
}

export function cancelOrder(orderId: number): Promise<Order> {
  return apiRequest<Order>(`/portfolio/orders/${orderId}/cancel`, { method: "POST" });
}

export function getWatchlist(): Promise<{ tickers: string[] }> {
  return apiRequest("/portfolio/watchlist");
}

export function addToWatchlist(ticker: string): Promise<{ tickers: string[] }> {
  return apiRequest(`/portfolio/watchlist/${ticker}`, { method: "POST" });
}

export function removeFromWatchlist(ticker: string): Promise<{ tickers: string[] }> {
  return apiRequest(`/portfolio/watchlist/${ticker}`, { method: "DELETE" });
}

export interface EquityCurve {
  dates: string[];
  equity: number[];
  note: string | null;
}

/** Real historical account value since the first deposit, reconstructed
 * server-side from the account's own transaction ledger — see
 * `backend/portfolio_history.py`. Never a simulated/smoothed line. */
export function getEquityCurve(): Promise<EquityCurve> {
  return apiRequest<EquityCurve>("/portfolio/equity-curve");
}

export interface HoldingContribution {
  ticker: string;
  contribution: number;
  contribution_pct: number | null;
  market_value: number;
  is_open_position: boolean;
}

export interface RegionContribution {
  region: string;
  contribution: number;
}

export interface AttributionMethodology {
  method: string;
  description: string;
  period: string;
  contribution_pct_minimum_total_return: number;
}

export interface AttributionResponse {
  status: "ok" | "insufficient_history";
  detail: string | null;
  total_return: number | null;
  holdings: HoldingContribution[];
  region_contributions: RegionContribution[];
  largest_contributor: HoldingContribution | null;
  largest_detractor: HoldingContribution | null;
  methodology: AttributionMethodology | null;
}

/** Which real holdings contributed to the account's real total return,
 * since inception — built from the same transaction ledger and live
 * prices as the rest of the app (see `backend/performance_attribution.py`),
 * never a second accounting model. */
export function getAttribution(): Promise<AttributionResponse> {
  return apiRequest<AttributionResponse>("/portfolio/attribution");
}
