/**
 * Diffs a target dollar allocation against current holdings to produce a
 * concrete list of BUY/SELL orders — the same delta-order math used by
 * Smart Invest, extracted here so Scenario Analysis reuses it instead of a
 * second copy. Pure function: no fetching, no execution.
 */

export interface ProposedOrder {
  ticker: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  value: number;
}

export function computeProposedOrders(
  targets: { ticker: string; targetValue: number }[],
  currentValueByTicker: Record<string, number>,
  priceByTicker: Record<string, number>,
  dustThreshold = 10,
): ProposedOrder[] {
  const orders: ProposedOrder[] = [];
  for (const { ticker, targetValue } of targets) {
    const price = priceByTicker[ticker];
    if (!price) continue;
    const currentValue = currentValueByTicker[ticker] ?? 0;
    const deltaValue = targetValue - currentValue;
    if (Math.abs(deltaValue) < dustThreshold) continue;
    orders.push({
      ticker,
      side: deltaValue > 0 ? "BUY" : "SELL",
      quantity: Math.abs(deltaValue) / price,
      price,
      value: Math.abs(deltaValue),
    });
  }
  // Sells first so they free up cash before any buy needs it.
  return orders.sort((a, b) => (a.side === "SELL" ? -1 : 1) - (b.side === "SELL" ? -1 : 1));
}
