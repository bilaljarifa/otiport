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
