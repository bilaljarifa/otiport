import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useWatchlist, useQuotes, useAlerts, watchlistKey, alertsKey } from "../lib/queries";
import { addToWatchlist, removeFromWatchlist, addAlert, removeAlert, resetAlert } from "../lib/portfolioApi";
import type { AlertDirection } from "../lib/portfolioApi";
import { money, signedMoney, signedPercent } from "../lib/format";
import { Link } from "react-router-dom";
import { QueryState } from "../components/QueryState";
import { Button } from "../components/Button";
import { Badge } from "../components/Badge";
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
        <div className="rounded-md border border-line overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
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
                      <div className="flex items-center justify-end gap-3">
                        <Link
                          to={`/app/research/${encodeURIComponent(ticker)}`}
                          className="text-xs font-semibold text-ink-muted hover:text-ink"
                        >
                          Research
                        </Link>
                        <Link
                          to={`/app/trading?ticker=${encodeURIComponent(ticker)}`}
                          className="text-xs font-semibold text-ink-muted hover:text-ink"
                        >
                          Trade
                        </Link>
                        <button
                          onClick={() => removeMutation.mutate(ticker)}
                          disabled={removeMutation.isPending && removeMutation.variables === ticker}
                          className="text-xs font-semibold text-ink-muted hover:text-down disabled:opacity-50"
                        >
                          {removeMutation.isPending && removeMutation.variables === ticker
                            ? "Removing…"
                            : "Remove"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </QueryState>

      <AlertsSection />
    </div>
  );
}

function AlertsSection() {
  const alerts = useAlerts();
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const [direction, setDirection] = useState<AlertDirection>("above");
  const [threshold, setThreshold] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: alertsKey });
  }

  const addMutation = useMutation({
    mutationFn: addAlert,
    onSuccess: () => {
      setTicker("");
      setThreshold("");
      invalidate();
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? (err.detail ?? err.message) : "Could not create alert.");
    },
  });
  const removeMutation = useMutation({ mutationFn: removeAlert, onSuccess: invalidate });
  const resetMutation = useMutation({ mutationFn: resetAlert, onSuccess: invalidate });

  function handleAdd(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const t = ticker.trim().toUpperCase();
    const th = Number(threshold);
    if (!TICKER_PATTERN.test(t)) {
      setFormError("Enter a valid ticker symbol (1-6 letters, e.g. SPY).");
      return;
    }
    if (!Number.isFinite(th) || th <= 0) {
      setFormError("Enter a positive price threshold.");
      return;
    }
    addMutation.mutate({ ticker: t, direction, threshold: th });
  }

  const items = alerts.data ?? [];

  return (
    <section className="rounded-md border border-line">
      <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">Price Alerts</div>
      <div className="p-4">
        <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Ticker
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="e.g. SPY"
              className="w-28 rounded border border-line-strong bg-surface px-3 py-2 text-sm font-mono uppercase text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Condition
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value as AlertDirection)}
              className="rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
            >
              <option value="above">Price rises above</option>
              <option value="below">Price falls below</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Threshold ($)
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="w-32 rounded border border-line-strong bg-surface px-3 py-2 text-sm font-mono text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10"
            />
          </label>
          <Button type="submit" disabled={addMutation.isPending}>
            {addMutation.isPending ? "Adding…" : "Add alert"}
          </Button>
        </form>
        {formError && <p className="mt-2 text-xs text-down">{formError}</p>}
        <p className="mt-2 text-xs text-ink-faint">
          Checked against live prices roughly once a minute while the app is open — not a push or
          email notification.
        </p>
      </div>

      <QueryState
        isLoading={alerts.isLoading}
        isError={alerts.isError}
        error={alerts.error}
        onRetry={() => void alerts.refetch()}
        isEmpty={items.length === 0}
        emptyMessage="No price alerts yet."
      >
        <div className="divide-y divide-line-soft border-t border-line">
          {items.map((a) => (
            <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-ink">{a.ticker}</span>
                  <span className="text-sm text-ink-muted">
                    {a.direction === "above" ? "above" : "below"} {money(a.threshold, 2)}
                  </span>
                  <Badge tone={a.status === "TRIGGERED" ? "bg-up-soft text-up" : "bg-accent-soft text-ink"}>
                    {a.status}
                  </Badge>
                </div>
                {a.status === "TRIGGERED" && a.triggered_at && (
                  <p className="mt-1 text-xs text-ink-faint">
                    Triggered {new Date(a.triggered_at).toLocaleString()}
                    {a.triggered_price != null && ` at ${money(a.triggered_price, 2)}`}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-3">
                {a.status === "TRIGGERED" && (
                  <button
                    onClick={() => resetMutation.mutate(a.id)}
                    disabled={resetMutation.isPending}
                    className="text-xs font-semibold text-ink-muted hover:text-ink"
                  >
                    Reset
                  </button>
                )}
                <button
                  onClick={() => removeMutation.mutate(a.id)}
                  disabled={removeMutation.isPending}
                  className="text-xs font-semibold text-ink-muted hover:text-down"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </QueryState>
    </section>
  );
}
