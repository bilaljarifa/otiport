import type { Position } from "./portfolioApi";
import type { Quote } from "./marketApi";

/**
 * Marks the account to market — deliberately the exact same formula as
 * `services/store.py::valuation()` on the Streamlit side (equity = market
 * value + cash, day P&L from previous close, total return vs. the
 * account's own `initial_cash`), so the two frontends never disagree
 * during migration. This is *display* math only, built from data the
 * backend already returned (positions from the DB, prices from
 * `/market/quotes`) — nothing here decides an order's fill price; that
 * happens exclusively in `backend/crud.py`.
 */

export interface Holding {
  ticker: string;
  quantity: number;
  avgPrice: number;
  price: number | null;
  marketValue: number | null;
  cost: number;
  pnl: number | null;
  pnlPct: number | null;
  dayPnl: number | null;
  weight: number | null;
}

export interface Valuation {
  equity: number;
  cash: number;
  marketValue: number;
  costBasis: number;
  pnl: number;
  pnlPct: number;
  dayPnl: number;
  dayPnlPct: number;
  totalReturn: number;
  totalReturnPct: number;
  investedPct: number;
  holdings: Holding[];
}

export function computeValuation(
  positions: Position[],
  quotes: Record<string, Quote>,
  cash: number,
  initialCash: number,
): Valuation {
  let marketValue = 0;
  let costBasis = 0;
  let dayPnl = 0;

  const holdings: Holding[] = positions.map((position) => {
    const quote = quotes[position.ticker];
    const cost = position.quantity * position.avg_price;
    costBasis += cost;

    if (!quote) {
      return {
        ticker: position.ticker,
        quantity: position.quantity,
        avgPrice: position.avg_price,
        price: null,
        marketValue: null,
        cost,
        pnl: null,
        pnlPct: null,
        dayPnl: null,
        weight: null,
      };
    }

    const value = position.quantity * quote.price;
    marketValue += value;
    const positionDayPnl = position.quantity * quote.change_abs;
    dayPnl += positionDayPnl;

    return {
      ticker: position.ticker,
      quantity: position.quantity,
      avgPrice: position.avg_price,
      price: quote.price,
      marketValue: value,
      cost,
      pnl: value - cost,
      pnlPct: cost ? (value / cost - 1) * 100 : null,
      dayPnl: positionDayPnl,
      weight: null, // filled below once total marketValue is known
    };
  });

  for (const holding of holdings) {
    if (holding.marketValue !== null && marketValue) {
      holding.weight = (holding.marketValue / marketValue) * 100;
    }
  }

  const equity = marketValue + cash;
  const pnl = marketValue - costBasis;
  const investedYesterday = marketValue - dayPnl;

  return {
    equity,
    cash,
    marketValue,
    costBasis,
    pnl,
    pnlPct: costBasis ? (pnl / costBasis) * 100 : 0,
    dayPnl,
    dayPnlPct: investedYesterday ? (dayPnl / investedYesterday) * 100 : 0,
    totalReturn: equity - initialCash,
    totalReturnPct: initialCash ? (equity / initialCash - 1) * 100 : 0,
    investedPct: equity ? (marketValue / equity) * 100 : 0,
    holdings: holdings.sort((a, b) => (b.marketValue ?? 0) - (a.marketValue ?? 0)),
  };
}
