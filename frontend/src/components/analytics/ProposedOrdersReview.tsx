import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { placeOrder } from "../../lib/portfolioApi";
import { ApiError } from "../../lib/apiClient";
import { money } from "../../lib/format";
import type { ProposedOrder } from "../../lib/orderPlanning";
import { Button } from "../Button";

interface ExecutionResult {
  ticker: string;
  side: string;
  status: string;
}

/**
 * Review → Confirm → Execute for a list of proposed orders — shared by
 * Smart Invest and Scenario Analysis so there is exactly one place that
 * calls the real trading endpoint. Every order still goes through
 * `POST /portfolio/orders` exactly as a manual trade would: this component
 * never fills or prices anything itself, it only sequences the same calls
 * a user clicking through Trading one order at a time would make.
 */
export function ProposedOrdersReview({
  orders,
  onCancel,
  helperText = "Orders execute one by one against your real simulated account via the existing order engine.",
}: {
  orders: ProposedOrder[];
  onCancel: () => void;
  helperText?: string;
}) {
  const queryClient = useQueryClient();
  const [executionLog, setExecutionLog] = useState<ExecutionResult[] | null>(null);

  const executeMutation = useMutation({
    mutationFn: async () => {
      const results: ExecutionResult[] = [];
      for (const order of orders) {
        try {
          const placed = await placeOrder({
            ticker: order.ticker,
            side: order.side,
            quantity: Number(order.quantity.toFixed(4)),
            order_type: "MARKET",
          });
          results.push({ ticker: order.ticker, side: order.side, status: placed.status });
        } catch (err) {
          results.push({
            ticker: order.ticker, side: order.side,
            status: err instanceof ApiError ? (err.detail ?? "ERROR") : "ERROR",
          });
        }
      }
      return results;
    },
    onSuccess: (results) => {
      setExecutionLog(results);
      void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["portfolio", "equity-curve"] });
      void queryClient.invalidateQueries({ queryKey: ["risk", "portfolio"] });
    },
  });

  if (executionLog) {
    return (
      <div className="rounded-md border border-line p-4">
        <div className="mb-3 text-sm font-bold text-ink">Execution result</div>
        <div className="flex flex-col gap-1.5 text-sm">
          {executionLog.map((r, i) => (
            <div key={i} className="flex items-center justify-between font-mono">
              <span>{r.side} {r.ticker}</span>
              <span className={r.status === "FILLED" ? "text-up" : "text-down"}>{r.status}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-ink-faint">Your portfolio, dashboard, and risk metrics now reflect these trades.</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-line">
      <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
        Review proposed orders ({orders.length})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
              <th className="px-4 py-2 font-semibold">Ticker</th>
              <th className="px-4 py-2 font-semibold">Side</th>
              <th className="px-4 py-2 font-semibold">Est. Qty</th>
              <th className="px-4 py-2 font-semibold">Est. Price</th>
              <th className="px-4 py-2 font-semibold">Est. Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft font-mono">
            {orders.map((o) => (
              <tr key={o.ticker}>
                <td className="px-4 py-2.5 font-sans font-semibold text-ink">{o.ticker}</td>
                <td className={`px-4 py-2.5 ${o.side === "BUY" ? "text-up" : "text-down"}`}>{o.side}</td>
                <td className="px-4 py-2.5">{o.quantity.toFixed(2)}</td>
                <td className="px-4 py-2.5">{money(o.price, 2)}</td>
                <td className="px-4 py-2.5">{money(o.value, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-line px-4 py-3">
        <Button onClick={() => executeMutation.mutate()} disabled={executeMutation.isPending}>
          {executeMutation.isPending ? "Executing…" : "Confirm & Execute Paper Trades"}
        </Button>
        <button
          onClick={onCancel}
          disabled={executeMutation.isPending}
          className="text-sm font-semibold text-ink-muted hover:text-ink"
        >
          Cancel
        </button>
        <span className="text-xs text-ink-faint sm:ml-auto">{helperText}</span>
      </div>
    </div>
  );
}
