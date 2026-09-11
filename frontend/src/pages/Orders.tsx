import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePortfolioSummary } from "../lib/queries";
import { cancelOrder } from "../lib/portfolioApi";
import type { OrderStatus } from "../lib/portfolioApi";
import { money } from "../lib/format";
import { QueryState } from "../components/QueryState";

const FILTERS: { value: OrderStatus | "ALL"; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "OPEN", label: "Open" },
  { value: "FILLED", label: "Filled" },
  { value: "CANCELLED", label: "Cancelled" },
  { value: "REJECTED", label: "Rejected" },
];

const STATUS_TONE: Record<OrderStatus, string> = {
  OPEN: "bg-accent-soft text-ink",
  FILLED: "bg-up-soft text-up",
  CANCELLED: "bg-surface-alt text-ink-muted",
  REJECTED: "bg-down-soft text-down",
};

export function OrdersPage() {
  const summary = usePortfolioSummary();
  const [filter, setFilter] = useState<OrderStatus | "ALL">("ALL");
  const queryClient = useQueryClient();

  const cancelMutation = useMutation({
    mutationFn: cancelOrder,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] }),
  });

  const orders = summary.data?.orders ?? [];
  const filtered = useMemo(
    () => (filter === "ALL" ? orders : orders.filter((o) => o.status === filter)),
    [orders, filter],
  );

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Orders</h1>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`rounded px-3 py-1.5 text-xs font-semibold ${
              filter === f.value
                ? "bg-accent-soft text-ink"
                : "text-ink-muted hover:bg-surface-alt hover:text-ink"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <QueryState
        isLoading={summary.isLoading}
        isError={summary.isError}
        error={summary.error}
        onRetry={() => void summary.refetch()}
        isEmpty={filtered.length === 0}
        emptyMessage={
          filter === "ALL" ? "No orders yet." : `No ${filter.toLowerCase()} orders.`
        }
      >
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                <th className="px-4 py-2 font-semibold">Ticker</th>
                <th className="px-4 py-2 font-semibold">Side</th>
                <th className="px-4 py-2 font-semibold">Qty</th>
                <th className="px-4 py-2 font-semibold">Type</th>
                <th className="px-4 py-2 font-semibold">Limit</th>
                <th className="px-4 py-2 font-semibold">Fill Price</th>
                <th className="px-4 py-2 font-semibold">Status</th>
                <th className="px-4 py-2 font-semibold">Placed</th>
                <th className="px-4 py-2 font-semibold"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft font-mono">
              {filtered.map((o) => (
                <tr key={o.id}>
                  <td className="px-4 py-2.5 font-sans font-semibold text-ink">{o.ticker}</td>
                  <td className={`px-4 py-2.5 ${o.side === "BUY" ? "text-up" : "text-down"}`}>
                    {o.side}
                  </td>
                  <td className="px-4 py-2.5">{o.quantity.toLocaleString()}</td>
                  <td className="px-4 py-2.5">{o.type}</td>
                  <td className="px-4 py-2.5">{o.limit_price ? money(o.limit_price, 2) : "—"}</td>
                  <td className="px-4 py-2.5">{o.fill_price ? money(o.fill_price, 2) : "—"}</td>
                  <td className="px-4 py-2.5 font-sans">
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[o.status]}`}>
                      {o.status}
                    </span>
                    {o.reject_reason && (
                      <span className="ml-2 text-xs text-ink-faint">{o.reject_reason}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink-faint">
                    {new Date(o.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-right font-sans">
                    {o.status === "OPEN" && (
                      <button
                        onClick={() => cancelMutation.mutate(o.id)}
                        disabled={cancelMutation.isPending && cancelMutation.variables === o.id}
                        className="text-xs font-semibold text-ink-muted hover:text-down disabled:opacity-50"
                      >
                        {cancelMutation.isPending && cancelMutation.variables === o.id
                          ? "Cancelling…"
                          : "Cancel"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </QueryState>
    </div>
  );
}
