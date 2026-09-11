import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePortfolioSummary, useQuotes } from "../lib/queries";
import { placeOrder } from "../lib/portfolioApi";
import type { Order, OrderSide, OrderType } from "../lib/portfolioApi";
import { ApiError } from "../lib/apiClient";
import { money, signedPercent } from "../lib/format";
import { ETF_UNIVERSE, TICKER_PATTERN } from "../lib/catalog";
import { QueryState } from "../components/QueryState";
import { buttonClass } from "../components/buttonStyles";

const INPUT_CLASS =
  "rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10";

/**
 * The paper-trading order ticket. Places a real order against the existing
 * FastAPI trading engine (`POST /portfolio/orders` -> `backend/crud.py`) —
 * MARKET orders fill immediately server-side at a backend-fetched price,
 * LIMIT orders sit OPEN until `AppShell`'s periodic settle matches them
 * against a fresh quote. Nothing here decides a fill price or pretends an
 * order succeeded; the order's returned `status`/`reject_reason` is shown
 * exactly as the backend reports it.
 */
export function TradingPage() {
  const [searchParams] = useSearchParams();
  const initialTicker = (searchParams.get("ticker") ?? "SPY").toUpperCase();

  const summary = usePortfolioSummary();
  const [ticker, setTicker] = useState(TICKER_PATTERN.test(initialTicker) ? initialTicker : "SPY");
  const [searchInput, setSearchInput] = useState("");
  const [side, setSide] = useState<OrderSide>("BUY");
  const [orderType, setOrderType] = useState<OrderType>("MARKET");
  const [quantity, setQuantity] = useState("1");
  const [limitPrice, setLimitPrice] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [lastOrder, setLastOrder] = useState<Order | null>(null);

  const quote = useQuotes([ticker]);
  const q = quote.data?.quotes[ticker];

  const position = summary.data?.positions.find((p) => p.ticker === ticker) ?? null;
  const cash = summary.data?.account.cash ?? 0;
  const openOrders = (summary.data?.orders ?? []).filter(
    (o) => o.status === "OPEN" && o.ticker === ticker,
  );

  const queryClient = useQueryClient();
  const orderMutation = useMutation({
    mutationFn: placeOrder,
    onSuccess: (order) => {
      setLastOrder(order);
      void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? (err.detail ?? err.message) : "Order failed.");
    },
  });

  function handleTickerSearch(event: FormEvent) {
    event.preventDefault();
    const candidate = searchInput.trim().toUpperCase();
    if (!TICKER_PATTERN.test(candidate)) {
      setFormError("Enter a valid ticker symbol (1-6 letters).");
      return;
    }
    setFormError(null);
    setLastOrder(null);
    setTicker(candidate);
    setSearchInput("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    setLastOrder(null);

    const qty = Number(quantity);
    if (!Number.isFinite(qty) || qty <= 0) {
      setFormError("Enter a quantity greater than zero.");
      return;
    }

    let limit: number | undefined;
    if (orderType === "LIMIT") {
      limit = Number(limitPrice);
      if (!Number.isFinite(limit) || limit <= 0) {
        setFormError("Enter a valid limit price.");
        return;
      }
    }

    orderMutation.mutate({
      ticker,
      side,
      quantity: qty,
      order_type: orderType,
      limit_price: limit,
    });
  }

  const qtyNumber = Number(quantity);
  const estimatedNotional = q && Number.isFinite(qtyNumber) ? qtyNumber * q.price : null;
  const maxAffordable = q && q.price > 0 ? Math.floor((cash / q.price) * 10000) / 10000 : null;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Trading</h1>

      <QueryState
        isLoading={summary.isLoading}
        isError={summary.isError}
        error={summary.error}
        onRetry={() => void summary.refetch()}
      >
        <div className="flex flex-col gap-6 lg:flex-row">
          <div className="flex flex-1 flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <form onSubmit={handleTickerSearch} className="flex items-center gap-2">
                <input
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Search ticker (e.g. SPY)"
                  className={`w-48 font-mono uppercase ${INPUT_CLASS}`}
                />
                <button type="submit" className={buttonClass("secondary", "px-3 py-1.5")}>
                  Go
                </button>
              </form>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {ETF_UNIVERSE.map((etf) => (
                <button
                  key={etf.ticker}
                  onClick={() => {
                    setTicker(etf.ticker);
                    setLastOrder(null);
                    setFormError(null);
                  }}
                  title={etf.name}
                  className={`rounded px-2.5 py-1 text-xs font-mono font-semibold ${
                    ticker === etf.ticker
                      ? "bg-accent-soft text-ink"
                      : "text-ink-muted hover:bg-surface-alt hover:text-ink"
                  }`}
                >
                  {etf.ticker}
                </button>
              ))}
            </div>

            <div className="rounded-md border border-line p-4">
              <div className="flex items-baseline justify-between">
                <span className="font-mono text-lg font-bold text-ink">{ticker}</span>
                {quote.isLoading ? (
                  <span className="text-xs text-ink-faint">Loading…</span>
                ) : q ? (
                  <span className="flex items-baseline gap-3 font-mono">
                    <span className="text-xl font-bold text-ink">{money(q.price, 2)}</span>
                    <span className={`text-sm font-semibold ${q.change_pct >= 0 ? "text-up" : "text-down"}`}>
                      {signedPercent(q.change_pct)}
                    </span>
                  </span>
                ) : (
                  <span className="text-xs text-ink-faint">Price unavailable</span>
                )}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <div>
                  <div className="text-xs uppercase tracking-wide text-ink-faint">Cash available</div>
                  <div className="font-mono font-semibold text-ink">{money(cash, 2)}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-ink-faint">Position held</div>
                  <div className="font-mono font-semibold text-ink">
                    {position ? position.quantity.toLocaleString() : "0"}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-ink-faint">Avg cost</div>
                  <div className="font-mono font-semibold text-ink">
                    {position ? money(position.avg_price, 2) : "—"}
                  </div>
                </div>
              </div>
            </div>

            {openOrders.length > 0 && (
              <div className="rounded-md border border-line">
                <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                  Open orders — {ticker}
                </div>
                <div className="divide-y divide-line-soft">
                  {openOrders.map((o) => (
                    <div key={o.id} className="flex items-center justify-between px-4 py-2 text-sm">
                      <span className={o.side === "BUY" ? "text-up" : "text-down"}>
                        {o.side} {o.quantity.toLocaleString()}
                      </span>
                      <span className="font-mono text-ink-muted">
                        {o.type} {o.limit_price ? `@ ${money(o.limit_price, 2)}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="w-full shrink-0 lg:w-80">
            <form
              onSubmit={handleSubmit}
              className="flex flex-col gap-4 rounded-md border border-line p-4"
            >
              <div className="text-sm font-bold text-ink">Order ticket · {ticker}</div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSide("BUY")}
                  className={`rounded px-3 py-2 text-sm font-bold ${
                    side === "BUY"
                      ? "border border-up bg-up-soft text-up"
                      : "border border-line-strong text-ink-muted hover:text-ink"
                  }`}
                >
                  Buy
                </button>
                <button
                  type="button"
                  onClick={() => setSide("SELL")}
                  className={`rounded px-3 py-2 text-sm font-bold ${
                    side === "SELL"
                      ? "border border-down bg-down-soft text-down"
                      : "border border-line-strong text-ink-muted hover:text-ink"
                  }`}
                >
                  Sell
                </button>
              </div>

              <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                Order type
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value as OrderType)}
                  className={INPUT_CLASS}
                >
                  <option value="MARKET">Market</option>
                  <option value="LIMIT">Limit</option>
                </select>
              </label>

              <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                Quantity
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className={`font-mono ${INPUT_CLASS}`}
                />
              </label>

              {orderType === "LIMIT" && (
                <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                  Limit price
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(e.target.value)}
                    placeholder={q ? q.price.toFixed(2) : ""}
                    className={`font-mono ${INPUT_CLASS}`}
                  />
                </label>
              )}

              <div className="flex flex-col gap-1 text-xs text-ink-faint">
                {estimatedNotional !== null && (
                  <span>
                    Estimated {side === "BUY" ? "cost" : "proceeds"}:{" "}
                    <span className="font-mono text-ink-muted">{money(estimatedNotional, 2)}</span>
                  </span>
                )}
                {side === "BUY" && maxAffordable !== null && (
                  <span>
                    Max affordable at current price:{" "}
                    <span className="font-mono text-ink-muted">{maxAffordable.toLocaleString()}</span>
                  </span>
                )}
                {side === "SELL" && (
                  <span>
                    Held: <span className="font-mono text-ink-muted">{position?.quantity ?? 0}</span>
                  </span>
                )}
              </div>

              {formError && (
                <p role="alert" className="rounded bg-down-soft px-3 py-2 text-sm text-down">
                  {formError}
                </p>
              )}

              {lastOrder && (
                <p
                  role="status"
                  className={`rounded px-3 py-2 text-sm ${
                    lastOrder.status === "FILLED"
                      ? "bg-up-soft text-up"
                      : lastOrder.status === "OPEN"
                        ? "bg-accent-soft text-ink"
                        : "bg-down-soft text-down"
                  }`}
                >
                  {lastOrder.status === "FILLED" &&
                    `Filled ${lastOrder.quantity.toLocaleString()} ${lastOrder.ticker} @ ${money(lastOrder.fill_price ?? 0, 2)}.`}
                  {lastOrder.status === "OPEN" && `Limit order placed and working.`}
                  {(lastOrder.status === "REJECTED" || lastOrder.status === "CANCELLED") &&
                    (lastOrder.reject_reason ?? "Order was not filled.")}
                </p>
              )}

              <button
                type="submit"
                disabled={orderMutation.isPending}
                className={buttonClass(side === "BUY" ? "accent" : "primary", "w-full")}
              >
                {orderMutation.isPending
                  ? "Placing order…"
                  : `${side === "BUY" ? "Buy" : "Sell"} ${ticker}`}
              </button>
            </form>
          </div>
        </div>
      </QueryState>
    </div>
  );
}
