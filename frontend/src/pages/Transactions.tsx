import { useMemo, useState } from "react";
import { usePortfolioSummary } from "../lib/queries";
import { money, signedMoney } from "../lib/format";
import { QueryState } from "../components/QueryState";

const TYPES = ["ALL", "DEPOSIT", "BUY", "SELL"] as const;

export function TransactionsPage() {
  const summary = usePortfolioSummary();
  const [filter, setFilter] = useState<(typeof TYPES)[number]>("ALL");

  const transactions = summary.data?.transactions ?? [];
  const filtered = useMemo(
    () => (filter === "ALL" ? transactions : transactions.filter((t) => t.type === filter)),
    [transactions, filter],
  );

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold text-ink">Transactions</h1>

      <div className="flex flex-wrap gap-1.5">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`rounded px-3 py-1.5 text-xs font-semibold ${
              filter === t
                ? "bg-accent-soft text-ink"
                : "text-ink-muted hover:bg-surface-alt hover:text-ink"
            }`}
          >
            {t === "ALL" ? "All" : t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      <QueryState
        isLoading={summary.isLoading}
        isError={summary.isError}
        error={summary.error}
        onRetry={() => void summary.refetch()}
        isEmpty={filtered.length === 0}
        emptyMessage="No transactions yet."
      >
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                <th className="px-4 py-2 font-semibold">Type</th>
                <th className="px-4 py-2 font-semibold">Ticker</th>
                <th className="px-4 py-2 font-semibold">Quantity</th>
                <th className="px-4 py-2 font-semibold">Price</th>
                <th className="px-4 py-2 font-semibold">Amount</th>
                <th className="px-4 py-2 font-semibold">Note</th>
                <th className="px-4 py-2 font-semibold">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft font-mono">
              {filtered.map((tx) => (
                <tr key={tx.id}>
                  <td className="px-4 py-2.5 font-sans font-semibold text-ink">{tx.type}</td>
                  <td className="px-4 py-2.5">{tx.ticker ?? "—"}</td>
                  <td className="px-4 py-2.5">{tx.quantity ? tx.quantity.toLocaleString() : "—"}</td>
                  <td className="px-4 py-2.5">{tx.price ? money(tx.price, 2) : "—"}</td>
                  <td className={`px-4 py-2.5 font-semibold ${tx.amount >= 0 ? "text-up" : "text-down"}`}>
                    {signedMoney(tx.amount, 2)}
                  </td>
                  <td className="px-4 py-2.5 font-sans text-ink-muted">{tx.note}</td>
                  <td className="px-4 py-2.5 text-xs text-ink-faint">
                    {new Date(tx.created_at).toLocaleString()}
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
