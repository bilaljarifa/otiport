import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useWatchlist, useQuotes, watchlistKey } from "../lib/queries";
import { addToWatchlist, removeFromWatchlist } from "../lib/portfolioApi";
import { money, signedMoney, signedPercent } from "../lib/format";
import { QueryState } from "../components/QueryState";
import { Button } from "../components/Button";
import { ApiError } from "../lib/apiClient";

const TICKER_PATTERN = /^[A-Z]{1,6}$/;

export function WatchlistPage() {
  const watchlist = useWatchlist();
  const tickers = watchlist.data?.tickers ?? [];
  const quotes = useQuotes(tickers);
  const queryClient = useQueryClient();

  const [input, setInput] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function invalidateAfterChange() {
    void queryClient.invalidateQueries({ queryKey: watchlistKey });
    void queryClient.invalidateQueries({ queryKey: ["portfolio", "summary"] });
  }

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: () => {
      setInput("");
      invalidateAfterChange();
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.detail ?? err.message : "Could not add ticker.");
    },
  });

  const removeMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: invalidateAfterChange,
  });

  function handleAdd(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const ticker = input.trim().toUpperCase();
    if (!TICKER_PATTERN.test(ticker)) {
      setFormError("Enter a valid ticker symbol (1-6 letters, e.g. SPY).");
      return;
    }
    if (tickers.includes(ticker)) {
      setFormError(`${ticker} is already on your watchlist.`);
      return;
    }
    addMutation.mutate(ticker);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-ink">Watchlist</h1>
      </div>

      <form onSubmit={handleAdd} className="flex items-start gap-3">
        <div className="flex flex-col gap-1">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Add ticker (e.g. SPY)"
            className="w-56 rounded border border-line-strong bg-surface px-3 py-2 text-sm font-mono uppercase text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
          />
          {formError && <p className="text-xs text-down">{formError}</p>}
        </div>
        <Button type="submit" disabled={addMutation.isPending}>
          {addMutation.isPending ? "Adding…" : "Add"}
        </Button>
      </form>

      <QueryState
        isLoading={watchlist.isLoading}
        isError={watchlist.isError}
        error={watchlist.error}
        onRetry={() => void watchlist.refetch()}
        isEmpty={tickers.length === 0}
        emptyMessage="No instruments on your watchlist yet. Add a ticker above to start tracking it."
      >
        <div className="rounded-md border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                <th className="px-4 py-2 font-semibold">Ticker</th>
                <th className="px-4 py-2 font-semibold">Price</th>
                <th className="px-4 py-2 font-semibold">Change</th>
                <th className="px-4 py-2 font-semibold">Change %</th>
                <th className="px-4 py-2 font-semibold"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft font-mono">
              {tickers.map((ticker) => {
                const quote = quotes.data?.quotes[ticker];
                const missing = quotes.data?.missing.includes(ticker);
                return (
                  <tr key={ticker}>
                    <td className="px-4 py-2.5 font-sans font-semibold text-ink">{ticker}</td>
                    {quotes.isLoading ? (
                      <td colSpan={3} className="px-4 py-2.5 text-xs text-ink-faint">
                        Loading…
                      </td>
                    ) : quote ? (
                      <>
                        <td className="px-4 py-2.5">{money(quote.price, 2)}</td>
                        <td className={`px-4 py-2.5 ${quote.change_abs >= 0 ? "text-up" : "text-down"}`}>
                          {signedMoney(quote.change_abs, 2)}
                        </td>
                        <td className={`px-4 py-2.5 ${quote.change_pct >= 0 ? "text-up" : "text-down"}`}>
                          {signedPercent(quote.change_pct)}
                        </td>
                      </>
                    ) : (
                      <td colSpan={3} className="px-4 py-2.5 text-xs text-ink-faint">
                        {missing ? "Price unavailable" : "—"}
                      </td>
                    )}
                    <td className="px-4 py-2.5 text-right font-sans">
                      <button
                        onClick={() => removeMutation.mutate(ticker)}
                        disabled={removeMutation.isPending && removeMutation.variables === ticker}
                        className="text-xs font-semibold text-ink-muted hover:text-down disabled:opacity-50"
                      >
                        {removeMutation.isPending && removeMutation.variables === ticker
                          ? "Removing…"
                          : "Remove"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </QueryState>
    </div>
  );
}
